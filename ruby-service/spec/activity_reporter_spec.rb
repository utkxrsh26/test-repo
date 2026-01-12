require 'spec_helper'
require 'rails_helper'
require_relative '../app/activity_reporter'

RSpec.describe ActivityReporter do
  let(:go_service_url) { 'http://go-service.test' }
  let(:python_service_url) { 'http://python-service.test' }
  let(:reporter) do
    described_class.new(
      go_service_url: go_service_url,
      python_service_url: python_service_url
    )
  end

  describe '#initialize' do
    it 'sets the service URLs' do
      instance = described_class.new(
        go_service_url: 'http://custom-go',
        python_service_url: 'http://custom-python'
      )

      expect(instance.instance_variable_get(:@go_service_url)).to eq('http://custom-go')
      expect(instance.instance_variable_get(:@python_service_url)).to eq('http://custom-python')
    end

    it 'uses default URLs when none are provided' do
      instance = described_class.new

      expect(instance.instance_variable_get(:@go_service_url)).to eq('http://localhost:8080')
      expect(instance.instance_variable_get(:@python_service_url)).to eq('http://localhost:8081')
    end
  end

  describe '#generate_report' do
    let(:user_id) { 123 }
    let(:activities) do
      [
        { 'timestamp' => '2024-01-01T10:00:00Z', 'action' => 'login' },
        { 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-02T09:30:00Z', 'action' => 'logout' }
      ]
    end
    let(:stats) do
      {
        total_actions: 3,
        unique_actions: 3,
        action_counts: { 'login' => 1, 'click' => 1, 'logout' => 1 },
        first_activity: '2024-01-01T10:00:00Z',
        last_activity: '2024-01-02T09:30:00Z',
        most_frequent: 'login'
      }
    end
    let(:patterns) do
      [
        { 'pattern_type' => 'daily', 'description' => 'Logs in daily', 'confidence' => 0.9 },
        { 'pattern_type' => 'morning', 'description' => 'Active in the morning', 'confidence' => 0.8 }
      ]
    end
    let(:user_score) { 80.5 }
    let(:anomalies) do
      [
        { 'timestamp' => '2024-01-03T03:00:00Z', 'action' => 'login', 'reason' => 'unusual time' }
      ]
    end

    before do
      allow(reporter).to receive(:fetch_user_activities).with(user_id).and_return(activities)
      allow(reporter).to receive(:fetch_activity_stats).with(user_id).and_return(stats)
      allow(reporter).to receive(:fetch_activity_patterns).with(activities).and_return(patterns)
      allow(reporter).to receive(:fetch_user_score).with(activities).and_return(user_score)
      allow(reporter).to receive(:fetch_anomalies).with(activities).and_return(anomalies)
      allow(Time).to receive(:now).and_return(Time.parse('2024-01-10T12:00:00Z'))
    end

    context 'when activities exist' do
      it 'returns a structured report hash with expected keys' do
        report = reporter.generate_report(user_id)

        expect(report).to be_a(Hash)
        expect(report[:user_id]).to eq(user_id)
        expect(report[:generated_at]).to eq('2024-01-10T12:00:00Z')
        expect(report[:summary]).to eq(
          total_actions: 3,
          unique_actions: 3,
          engagement_score: user_score,
          first_activity: '2024-01-01T10:00:00Z',
          last_activity: '2024-01-02T09:30:00Z'
        )
        expect(report[:action_breakdown]).to eq(stats[:action_counts])
        expect(report[:patterns]).to eq(
          [
            { type: 'daily', description: 'Logs in daily', confidence: 0.9 },
            { type: 'morning', description: 'Active in the morning', confidence: 0.8 }
          ]
        )
        expect(report[:anomalies]).to eq(anomalies)
        expect(report[:timeline]).to be_an(Array)
        expect(report[:insights]).to be_an(Array)
      end

      it 'passes group_by option to format_timeline' do
        expect(reporter).to receive(:format_timeline).with(activities, :week).and_call_original

        reporter.generate_report(user_id, group_by: :week)
      end

      it 'defaults group_by to :day when not provided' do
        expect(reporter).to receive(:format_timeline).with(activities, :day).and_call_original

        reporter.generate_report(user_id)
      end
    end

    context 'when no activities are found' do
      before do
        allow(reporter).to receive(:fetch_user_activities).with(user_id).and_return([])
        allow(Time).to receive(:now).and_return(Time.parse('2024-01-10T12:00:00Z'))
      end

      it 'returns an error report' do
        report = reporter.generate_report(user_id)

        expect(report[:error]).to eq(true)
        expect(report[:message]).to eq('No activities found')
        expect(report[:generated_at]).to eq('2024-01-10T12:00:00Z')
      end
    end
  end

  describe '#format_timeline' do
    let(:activities) do
      [
        { 'timestamp' => '2024-01-01T10:15:00Z', 'action' => 'login' },
        { 'timestamp' => '2024-01-01T10:45:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-02T09:30:00Z', 'action' => 'logout' }
      ]
    end

    context 'when activities array is empty' do
      it 'returns an empty array' do
        result = reporter.format_timeline([])

        expect(result).to eq([])
      end
    end

    context 'when grouping by day' do
      it 'groups activities by date and aggregates counts' do
        result = reporter.format_timeline(activities, :day)

        expect(result.size).to eq(2)

        day1 = result.find { |r| r[:period] == '2024-01-01' }
        day2 = result.find { |r| r[:period] == '2024-01-02' }

        expect(day1[:total_actions]).to eq(3)
        expect(day1[:actions]).to eq('login' => 1, 'click' => 2)
        expect(day1[:first_timestamp]).to eq('2024-01-01T10:15:00Z')
        expect(day1[:last_timestamp]).to eq('2024-01-01T11:00:00Z')

        expect(day2[:total_actions]).to eq(1)
        expect(day2[:actions]).to eq('logout' => 1)
        expect(day2[:first_timestamp]).to eq('2024-01-02T09:30:00Z')
        expect(day2[:last_timestamp]).to eq('2024-01-02T09:30:00Z')
      end
    end

    context 'when grouping by hour' do
      it 'groups activities by hour' do
        result = reporter.format_timeline(activities, :hour)

        expect(result.map { |r| r[:period] }).to contain_exactly(
          '2024-01-01 10:00',
          '2024-01-01 11:00',
          '2024-01-02 09:00'
        )

        hour10 = result.find { |r| r[:period] == '2024-01-01 10:00' }
        expect(hour10[:total_actions]).to eq(2)
        expect(hour10[:actions]).to eq('login' => 1, 'click' => 1)
      end
    end

    context 'when grouping by week' do
      it 'groups activities by ISO week' do
        result = reporter.format_timeline(activities, :week)

        expect(result.size).to eq(1)
        expect(result.first[:period]).to eq('2024-W01')
        expect(result.first[:total_actions]).to eq(4)
      end
    end

    context 'when grouping by month' do
      it 'groups activities by month' do
        result = reporter.format_timeline(activities, :month)

        expect(result.size).to eq(1)
        expect(result.first[:period]).to eq('2024-01')
        expect(result.first[:total_actions]).to eq(4)
      end
    end

    context 'when grouping by an unknown key' do
      it 'defaults to grouping by day' do
        result = reporter.format_timeline(activities, :unknown)

        expect(result.map { |r| r[:period] }).to contain_exactly('2024-01-01', '2024-01-02')
      end
    end

    context 'ordering of periods' do
      let(:unordered_activities) do
        [
          { 'timestamp' => '2024-01-03T10:00:00Z', 'action' => 'a' },
          { 'timestamp' => '2024-01-01T10:00:00Z', 'action' => 'b' },
          { 'timestamp' => '2024-01-02T10:00:00Z', 'action' => 'c' }
        ]
      end

      it 'sorts the result by period' do
        result = reporter.format_timeline(unordered_activities, :day)

        expect(result.map { |r| r[:period] }).to eq(
          ['2024-01-01', '2024-01-02', '2024-01-03']
        )
      end
    end
  end

  describe '#export_to_json' do
    let(:report_hash) do
      {
        user_id: 1,
        summary: { total_actions: 5 }
      }
    end

    context 'when filepath is not provided' do
      it 'returns success and JSON data' do
        result = reporter.export_to_json(report_hash)

        expect(result[:success]).to eq(true)
        expect(result[:data]).to be_a(String)
        parsed = JSON.parse(result[:data])
        expect(parsed['user_id']).to eq(1)
        expect(parsed['summary']['total_actions']).to eq(5)
      end
    end

    context 'when filepath is provided' do
      let(:filepath) { 'tmp/test_report.json' }

      before do
        allow(File).to receive(:write).and_return(100)
      end

      it 'writes JSON to the file and returns metadata' do
        result = reporter.export_to_json(report_hash, filepath)

        expect(File).to have_received(:write) do |path, data|
          expect(path).to eq(filepath)
          expect(JSON.parse(data)['user_id']).to eq(1)
        end

        expect(result[:success]).to eq(true)
        expect(result[:filepath]).to eq(filepath)
        expect(result[:size]).to be_a(Integer)
        expect(result[:size]).to be > 0
      end
    end

    context 'when an error occurs during file write' do
      let(:filepath) { 'tmp/test_report_error.json' }

      before do
        allow(File).to receive(:write).and_raise(StandardError.new('disk full'))
      end

      it 'returns a failure hash with error message' do
        result = reporter.export_to_json(report_hash, filepath)

        expect(result[:success]).to eq(false)
        expect(result[:error]).to eq('disk full')
      end
    end
  end

  describe '#compare_users' do
    let(:user_ids) { [1, 2, 3] }

    context 'when fewer than 2 users are provided' do
      it 'returns an error report' do
        allow(Time).to receive(:now).and_return(Time.parse('2024-01-10T12:00:00Z'))

        result = reporter.compare_users([1])

        expect(result[:error]).to eq(true)
        expect(result[:message]).to eq('At least 2 users required')
        expect(result[:generated_at]).to eq('2024-01-10T12:00:00Z')
      end
    end

    context 'when multiple users are provided' do
      let(:activities_user1) { [{ 'timestamp' => '2024-01-01T10:00:00Z', 'action' => 'a' }] }
      let(:activities_user2) { [{ 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'b' }] }
      let(:activities_user3) { [{ 'timestamp' => '2024-01-01T12:00:00Z', 'action' => 'c' }] }

      let(:stats_user1) do
        {
          total_actions: 10,
          unique_actions: 2,
          action_counts: { 'a' => 10 },
          first_activity: '2024-01-01T10:00:00Z',
          last_activity: '2024-01-01T10:30:00Z',
          most_frequent: 'a'
        }
      end

      let(:stats_user2) do
        {
          total_actions: 5,
          unique_actions: 1,
          action_counts: { 'b' => 5 },
          first_activity: '2024-01-01T11:00:00Z',
          last_activity: '2024-01-01T11:30:00Z',
          most_frequent: 'b'
        }
      end

      let(:stats_user3) do
        {
          total_actions: 20,
          unique_actions: 3,
          action_counts: { 'c' => 20 },
          first_activity: '2024-01-01T12:00:00Z',
          last_activity: '2024-01-01T12:30:00Z',
          most_frequent: 'c'
        }
      end

      before do
        allow(reporter).to receive(:fetch_user_activities).with(1).and_return(activities_user1)
        allow(reporter).to receive(:fetch_user_activities).with(2).and_return(activities_user2)
        allow(reporter).to receive(:fetch_user_activities).with(3).and_return(activities_user3)

        allow(reporter).to receive(:fetch_activity_stats).with(1).and_return(stats_user1)
        allow(reporter).to receive(:fetch_activity_stats).with(2).and_return(stats_user2)
        allow(reporter).to receive(:fetch_activity_stats).with(3).and_return(stats_user3)

        allow(reporter).to receive(:fetch_user_score).with(activities_user1).and_return(50.0)
        allow(reporter).to receive(:fetch_user_score).with(activities_user2).and_return(75.0)
        allow(reporter).to receive(:fetch_user_score).with(activities_user3).and_return(25.0)
      end

      it 'returns comparison data for all users' do
        result = reporter.compare_users(user_ids)

        expect(result[:total_users]).to eq(3)
        expect(result[:comparisons].size).to eq(3)

        comparison_user1 = result[:comparisons].find { |c| c[:user_id] == 1 }
        comparison_user2 = result[:comparisons].find { |c| c[:user_id] == 2 }
        comparison_user3 = result[:comparisons].find { |c| c[:user_id] == 3 }

        expect(comparison_user1[:total_actions]).to eq(10)
        expect(comparison_user1[:engagement_score]).to eq(50.0)
        expect(comparison_user1[:most_frequent_action]).to eq('a')

        expect(comparison_user2[:total_actions]).to eq(5)
        expect(comparison_user2[:engagement_score]).to eq(75.0)
        expect(comparison_user2[:most_frequent_action]).to eq('b')

        expect(comparison_user3[:total_actions]).to eq(20)
        expect(comparison_user3[:engagement_score]).to eq(25.0)
        expect(comparison_user3[:most_frequent_action]).to eq('c')
      end

      it 'sorts comparisons by engagement_score descending and sets top_user' do
        result = reporter.compare_users(user_ids)

        scores = result[:comparisons].map { |c| c[:engagement_score] }
        expect(scores).to eq(scores.sort.reverse)

        expect(result[:top_user]).to eq(2)
      end

      it 'calculates the average engagement score' do
        result = reporter.compare_users(user_ids)

        expected_average = ((50.0 + 75.0 + 25.0) / 3.0).round(2)
        expect(result[:average_score]).to eq(expected_average)
      end
    end
  end
end
