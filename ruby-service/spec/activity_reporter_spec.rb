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

  let(:user_id) { 123 }

  describe '#initialize' do
    context 'with default arguments' do
      let(:reporter) { described_class.new }

      it 'sets default go_service_url' do
        expect(reporter.instance_variable_get(:@go_service_url)).to eq('http://localhost:8080')
      end

      it 'sets default python_service_url' do
        expect(reporter.instance_variable_get(:@python_service_url)).to eq('http://localhost:8081')
      end
    end

    context 'with custom arguments' do
      it 'sets custom go_service_url' do
        expect(reporter.instance_variable_get(:@go_service_url)).to eq(go_service_url)
      end

      it 'sets custom python_service_url' do
        expect(reporter.instance_variable_get(:@python_service_url)).to eq(python_service_url)
      end
    end
  end

  describe '#generate_report' do
    let(:activities) do
      [
        { 'timestamp' => '2024-01-01T10:00:00Z', 'action' => 'login' },
        { 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-02T09:00:00Z', 'action' => 'logout' }
      ]
    end

    let(:stats) do
      {
        total_actions: 3,
        unique_actions: 3,
        action_counts: { 'login' => 1, 'click' => 1, 'logout' => 1 },
        first_activity: '2024-01-01T10:00:00Z',
        last_activity: '2024-01-02T09:00:00Z',
        most_frequent: 'login'
      }
    end

    let(:patterns) do
      [
        { 'pattern_type' => 'daily', 'description' => 'Active every day', 'confidence' => 0.9 },
        { 'pattern_type' => 'morning', 'description' => 'Active in the morning', 'confidence' => 0.8 }
      ]
    end

    let(:user_score) { 80.0 }
    let(:anomalies) do
      [
        { 'timestamp' => '2024-01-02T09:00:00Z', 'reason' => 'suspicious' }
      ]
    end

    before do
      allow(reporter).to receive(:fetch_user_activities).with(user_id).and_return(activities)
      allow(reporter).to receive(:fetch_activity_stats).with(user_id).and_return(stats)
      allow(reporter).to receive(:fetch_activity_patterns).with(activities).and_return(patterns)
      allow(reporter).to receive(:fetch_user_score).with(activities).and_return(user_score)
      allow(reporter).to receive(:fetch_anomalies).with(activities).and_return(anomalies)
      allow(Time).to receive(:now).and_return(Time.parse('2024-01-03T12:00:00Z'))
    end

    context 'when user has no activities' do
      before do
        allow(reporter).to receive(:fetch_user_activities).with(user_id).and_return([])
      end

      it 'returns an error report' do
        result = reporter.generate_report(user_id)
        expect(result[:error]).to be true
        expect(result[:message]).to eq('No activities found')
        expect(result[:generated_at]).to eq('2024-01-03T12:00:00Z')
      end
    end

    context 'when user has activities' do
      it 'returns a report hash with expected top-level keys' do
        result = reporter.generate_report(user_id)
        expect(result[:user_id]).to eq(user_id)
        expect(result[:generated_at]).to eq('2024-01-03T12:00:00Z')
        expect(result).to have_key(:summary)
        expect(result).to have_key(:action_breakdown)
        expect(result).to have_key(:patterns)
        expect(result).to have_key(:anomalies)
        expect(result).to have_key(:timeline)
        expect(result).to have_key(:insights)
      end

      it 'includes summary data from stats and user_score' do
        result = reporter.generate_report(user_id)
        summary = result[:summary]
        expect(summary[:total_actions]).to eq(3)
        expect(summary[:unique_actions]).to eq(3)
        expect(summary[:engagement_score]).to eq(80.0)
        expect(summary[:first_activity]).to eq('2024-01-01T10:00:00Z')
        expect(summary[:last_activity]).to eq('2024-01-02T09:00:00Z')
      end

      it 'includes action_breakdown from stats' do
        result = reporter.generate_report(user_id)
        expect(result[:action_breakdown]).to eq(stats[:action_counts])
      end

      it 'formats patterns using format_pattern' do
        result = reporter.generate_report(user_id)
        expect(result[:patterns]).to eq(
          [
            { type: 'daily', description: 'Active every day', confidence: 0.9 },
            { type: 'morning', description: 'Active in the morning', confidence: 0.8 }
          ]
        )
      end

      it 'includes anomalies as returned by fetch_anomalies' do
        result = reporter.generate_report(user_id)
        expect(result[:anomalies]).to eq(anomalies)
      end

      it 'builds a timeline grouped by day by default' do
        result = reporter.generate_report(user_id)
        timeline = result[:timeline]
        expect(timeline.size).to eq(2)
        expect(timeline.map { |e| e[:period] }).to eq(%w[2024-01-01 2024-01-02])
      end

      it 'passes group_by option to format_timeline' do
        expect(reporter).to receive(:format_timeline).with(activities, :hour).and_call_original
        reporter.generate_report(user_id, group_by: :hour)
      end

      it 'generates insights based on stats, patterns, user_score, and anomalies' do
        result = reporter.generate_report(user_id)
        insights = result[:insights]
        expect(insights).to be_an(Array)
        expect(insights).not_to be_empty
      end
    end
  end

  describe '#format_timeline' do
    let(:activities) do
      [
        { 'timestamp' => '2024-01-01T10:15:00Z', 'action' => 'login' },
        { 'timestamp' => '2024-01-01T10:45:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-02T09:00:00Z', 'action' => 'logout' }
      ]
    end

    context 'when activities array is empty' do
      it 'returns an empty array' do
        result = reporter.format_timeline([])
        expect(result).to eq([])
      end
    end

    context 'when grouping by day' do
      it 'groups activities by date string' do
        result = reporter.format_timeline(activities, :day)
        expect(result.size).to eq(2)
        expect(result.map { |e| e[:period] }).to eq(%w[2024-01-01 2024-01-02])
      end

      it 'includes total_actions and actions breakdown per period' do
        result = reporter.format_timeline(activities, :day)
        day1 = result.find { |e| e[:period] == '2024-01-01' }
        day2 = result.find { |e| e[:period] == '2024-01-02' }

        expect(day1[:total_actions]).to eq(3)
        expect(day1[:actions]).to eq('login' => 1, 'click' => 2)

        expect(day2[:total_actions]).to eq(1)
        expect(day2[:actions]).to eq('logout' => 1)
      end

      it 'includes first_timestamp and last_timestamp from activities in that period' do
        result = reporter.format_timeline(activities, :day)
        day1 = result.find { |e| e[:period] == '2024-01-01' }

        expect(day1[:first_timestamp]).to eq('2024-01-01T10:15:00Z')
        expect(day1[:last_timestamp]).to eq('2024-01-01T11:00:00Z')
      end

      it 'sorts entries by period ascending' do
        shuffled = activities.reverse
        result = reporter.format_timeline(shuffled, :day)
        expect(result.map { |e| e[:period] }).to eq(%w[2024-01-01 2024-01-02])
      end
    end

    context 'when grouping by hour' do
      it 'groups by hour with format YYYY-MM-DD HH:00' do
        result = reporter.format_timeline(activities, :hour)
        expect(result.map { |e| e[:period] }).to eq(
          ['2024-01-01 10:00', '2024-01-01 11:00', '2024-01-02 09:00']
        )
      end
    end

    context 'when grouping by week' do
      it 'groups by ISO week with format YYYY-WVV' do
        result = reporter.format_timeline(activities, :week)
        expect(result.map { |e| e[:period] }.uniq).to eq(['2024-W01'])
      end
    end

    context 'when grouping by month' do
      it 'groups by month with format YYYY-MM' do
        result = reporter.format_timeline(activities, :month)
        expect(result.map { |e| e[:period] }.uniq).to eq(['2024-01'])
      end
    end

    context 'when grouping by unknown key' do
      it 'falls back to grouping by day' do
        result = reporter.format_timeline(activities, :unknown)
        expect(result.map { |e| e[:period] }).to eq(%w[2024-01-01 2024-01-02])
      end
    end

    context 'when timestamps are invalid' do
      let(:activities_with_invalid) do
        [
          { 'timestamp' => 'invalid-timestamp', 'action' => 'login' }
        ]
      end

      it 'uses parse_timestamp which falls back to Time.now' do
        allow(Time).to receive(:now).and_return(Time.parse('2024-01-05T00:00:00Z'))
        result = reporter.format_timeline(activities_with_invalid, :day)
        expect(result.first[:period]).to eq('2024-01-05')
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
      it 'returns success with JSON data' do
        result = reporter.export_to_json(report_hash)
        expect(result[:success]).to be true
        expect(result[:data]).to be_a(String)
        parsed = JSON.parse(result[:data])
        expect(parsed['user_id']).to eq(1)
        expect(parsed['summary']['total_actions']).to eq(5)
      end
    end

    context 'when filepath is provided' do
      let(:filepath) { File.join(Dir.tmpdir, "activity_report_#{SecureRandom.hex(4)}.json") }

      after do
        File.delete(filepath) if File.exist?(filepath)
      end

      it 'writes JSON to the file and returns metadata' do
        result = reporter.export_to_json(report_hash, filepath)
        expect(result[:success]).to be true
        expect(result[:filepath]).to eq(filepath)
        expect(result[:size]).to be > 0
        expect(File).to exist(filepath)
        file_content = File.read(filepath)
        parsed = JSON.parse(file_content)
        expect(parsed['user_id']).to eq(1)
      end
    end

    context 'when an error occurs during file write' do
      let(:filepath) { '/invalid/path/report.json' }

      it 'returns a failure hash with error message' do
        allow(File).to receive(:write).and_raise(StandardError.new('disk full'))
        result = reporter.export_to_json(report_hash, filepath)
        expect(result[:success]).to be false
        expect(result[:error]).to eq('disk full')
      end
    end
  end

  describe '#compare_users' do
    let(:user_ids) { [1, 2, 3] }

    let(:activities_user1) do
      [
        { 'timestamp' => '2024-01-01T10:00:00Z', 'action' => 'login' }
      ]
    end

    let(:activities_user2) do
      [
        { 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-01T12:00:00Z', 'action' => 'click' }
      ]
    end

    let(:activities_user3) do
      [
        { 'timestamp' => '2024-01-02T09:00:00Z', 'action' => 'logout' }
      ]
    end

    let(:stats_user1) do
      {
        total_actions: 1,
        unique_actions: 1,
        action_counts: { 'login' => 1 },
        first_activity: '2024-01-01T10:00:00Z',
        last_activity: '2024-01-01T10:00:00Z',
        most_frequent: 'login'
      }
    end

    let(:stats_user2) do
      {
        total_actions: 2,
        unique_actions: 1,
        action_counts: { 'click' => 2 },
        first_activity: '2024-01-01T11:00:00Z',
        last_activity: '2024-01-01T12:00:00Z',
        most_frequent: 'click'
      }
    end

    let(:stats_user3) do
      {
        total_actions: 1,
        unique_actions: 1,
        action_counts: { 'logout' => 1 },
        first_activity: '2024-01-02T09:00:00Z',
        last_activity: '2024-01-02T09:00:00Z',
        most_frequent: 'logout'
      }
    end

    before do
      allow(reporter).to receive(:fetch_user_activities).with(1).and_return(activities_user1)
      allow(reporter).to receive(:fetch_user_activities).with(2).and_return(activities_user2)
      allow(reporter).to receive(:fetch_user_activities).with(3).and_return(activities_user3)

      allow(reporter).to receive(:fetch_activity_stats).with(1).and_return(stats_user1)
      allow(reporter).to receive(:fetch_activity_stats).with(2).and_return(stats_user2)
      allow(reporter).to receive(:fetch_activity_stats).with(3).and_return(stats_user3)

      allow(reporter).to receive(:fetch_user_score).with(activities_user1).and_return(10.0)
      allow(reporter).to receive(:fetch_user_score).with(activities_user2).and_return(90.0)
      allow(reporter).to receive(:fetch_user_score).with(activities_user3).and_return(50.0)
    end

    context 'when fewer than 2 user_ids are provided' do
      it 'returns an error report' do
        result = reporter.compare_users([1])
        expect(result[:error]).to be true
        expect(result[:message]).to eq('At least 2 users required')
        expect(result[:generated_at]).to be_a(String)
      end
    end

    context 'when multiple users are provided' do
      it 'returns total_users equal to number of user_ids' do
        result = reporter.compare_users(user_ids)
        expect(result[:total_users]).to eq(3)
      end

      it 'returns comparisons sorted by engagement_score descending' do
        result = reporter.compare_users(user_ids)
        comparisons = result[:comparisons]
        expect(comparisons.map { |c| c[:user_id] }).to eq([2, 3, 1])
        expect(comparisons.map { |c| c[:engagement_score] }).to eq([90.0, 50.0, 10.0])
      end

      it 'includes total_actions and most_frequent_action from stats' do
        result = reporter.compare_users(user_ids)
        user2_comp = result[:comparisons].find { |c| c[:user_id] == 2 }
        expect(user2_comp[:total_actions]).to eq(2)
        expect(user2_comp[:most_frequent_action]).to eq('click')
      end

      it 'sets top_user to the user with highest engagement_score' do
        result = reporter.compare_users(user_ids)
        expect(result[:top_user]).to eq(2)
      end

      it 'calculates average_score correctly' do
        result = reporter.compare_users(user_ids)
        expect(result[:average_score]).to eq(((10.0 + 90.0 + 50.0) / 3.0).round(2))
      end
    end
  end

  describe '#format_pattern' do
    let(:pattern) do
      {
        'pattern_type' => 'daily',
        'description' => 'Active every day',
        'confidence' => 0.95
      }
    end

    it 'maps pattern keys to expected symbolized keys' do
      result = reporter.send(:format_pattern, pattern)
      expect(result).to eq(
        type: 'daily',
        description: 'Active every day',
        confidence: 0.95
      )
    end
  end

  describe '#generate_insights' do
    let(:stats) do
      {
        total_actions: total_actions,
        unique_actions: unique_actions,
        action_counts: {},
        first_activity: '2024-01-01T10:00:00Z',
        last_activity: '2024-01-02T10:00:00Z',
        most_frequent: 'login'
      }
    end

    let(:patterns) { Array.new(pattern_count) { {} } }
    let(:anomalies) { Array.new(anomaly_count) { {} } }

    let(:total_actions) { 10 }
    let(:unique_actions) { 5 }
    let(:pattern_count) { 1 }
    let(:anomaly_count) { 0 }
    let(:user_score) { 10.0 }

    subject(:insights) do
      reporter.send(:generate_insights, stats, patterns, user_score, anomalies)
    end

    context 'when user_score is low' do
      let(:user_score) { 10.0 }

      it 'includes low engagement insight' do
        expect(insights).to include('Low engagement - consider re-engagement strategies')
      end
    end

    context 'when user_score is moderately high' do
      let(:user_score) { 60.0 }

      it 'includes moderate engagement insight' do
        expect(insights).to include('Moderately engaged user with regular activity')
      end
    end

    context 'when user_score is very high' do
      let(:user_score) { 80.0 }

      it 'includes highly engaged insight' do
        expect(insights).to include('Highly engaged user with strong activity patterns')
      end
    end

    context 'when unique_actions is greater than 10' do
      let(:unique_actions) { 11 }

      it 'includes diverse activity profile insight' do
        expect(insights).to include('Diverse activity profile across multiple action types')
      end
    end

    context 'when more than 2 patterns exist' do
      let(:pattern_count) { 3 }

      it 'includes clear behavioral patterns insight' do
        expect(insights).to include('Clear behavioral patterns detected')
      end
    end

    context 'when anomalies exist' do
      let(:anomaly_count) { 2 }

      it 'includes anomalies insight with count' do
        expect(insights).to include('2 anomalous activities detected - review recommended')
      end
    end

    context 'when total_actions is greater than 100' do
      let(:total_actions) { 150 }

      it 'includes power user insight' do
        expect(insights).to include('Power user - high volume of activities')
      end
    end
  end

  describe '#parse_timestamp' do
    context 'with a valid timestamp string' do
      it 'parses and returns a Time object' do
        result = reporter.send(:parse_timestamp, '2024-01-01T10:00:00Z')
        expect(result).to be_a(Time)
        expect(result.utc.iso8601).to eq('2024-01-01T10:00:00Z')
      end
    end

    context 'with an invalid timestamp string' do
      it 'returns Time.now as fallback' do
        allow(Time).to receive(:now).and_return(Time.parse('2024-01-05T00:00:00Z'))
        result = reporter.send(:parse_timestamp, 'invalid-timestamp')
        expect(result).to eq(Time.parse('2024-01-05T00:00:00Z'))
      end
    end
  end

  describe '#error_report' do
    it 'returns an error hash with message and generated_at' do
      allow(Time).to receive(:now).and_return(Time.parse('2024-01-03T12:00:00Z'))
      result = reporter.send(:error_report, 'Something went wrong')
      expect(result[:error]).to be true
      expect(result[:message]).to eq('Something went wrong')
      expect(result[:generated_at]).to eq('2024-01-03T12:00:00Z')
    end
  end
end
