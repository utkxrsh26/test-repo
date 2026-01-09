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

  let(:user_id) { 'user-123' }

  let(:activities) do
    [
      { 'timestamp' => '2024-01-01T10:15:00Z', 'action' => 'login' },
      { 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'click' },
      { 'timestamp' => '2024-01-02T09:30:00Z', 'action' => 'purchase' },
      { 'timestamp' => '2024-01-02T10:00:00Z', 'action' => 'click' }
    ]
  end

  let(:stats) do
    {
      total_actions: 4,
      unique_actions: 3,
      action_counts: { 'login' => 1, 'click' => 2, 'purchase' => 1 },
      first_activity: '2024-01-01T10:15:00Z',
      last_activity: '2024-01-02T10:00:00Z',
      most_frequent: 'click'
    }
  end

  let(:patterns) do
    [
      { 'pattern_type' => 'daily_login', 'description' => 'Logs in daily', 'confidence' => 0.9 },
      { 'pattern_type' => 'buyer', 'description' => 'Frequently purchases', 'confidence' => 0.8 }
    ]
  end

  let(:user_score) { 80.0 }

  let(:anomalies) do
    [
      { 'timestamp' => '2024-01-03T00:00:00Z', 'action' => 'suspicious_login' }
    ]
  end

  describe '#initialize' do
    context 'with default arguments' do
      let(:reporter_default) { described_class.new }

      it 'sets default go_service_url' do
        expect(reporter_default.instance_variable_get(:@go_service_url)).to eq('http://localhost:8080')
      end

      it 'sets default python_service_url' do
        expect(reporter_default.instance_variable_get(:@python_service_url)).to eq('http://localhost:8081')
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
    before do
      allow(reporter).to receive(:fetch_user_activities).with(user_id).and_return(activities)
      allow(reporter).to receive(:fetch_activity_stats).with(user_id).and_return(stats)
      allow(reporter).to receive(:fetch_activity_patterns).with(activities).and_return(patterns)
      allow(reporter).to receive(:fetch_user_score).with(activities).and_return(user_score)
      allow(reporter).to receive(:fetch_anomalies).with(activities).and_return(anomalies)
      allow(Time).to receive(:now).and_return(Time.parse('2024-01-10T12:00:00Z'))
    end

    context 'when activities exist' do
      it 'returns a hash with expected top-level keys' do
        report = reporter.generate_report(user_id)

        expect(report).to include(
          :user_id,
          :generated_at,
          :summary,
          :action_breakdown,
          :patterns,
          :anomalies,
          :timeline,
          :insights
        )
      end

      it 'includes the correct user_id' do
        report = reporter.generate_report(user_id)
        expect(report[:user_id]).to eq(user_id)
      end

      it 'sets generated_at to current time in ISO8601 format' do
        report = reporter.generate_report(user_id)
        expect(report[:generated_at]).to eq('2024-01-10T12:00:00Z')
      end

      it 'builds summary from stats and user_score' do
        report = reporter.generate_report(user_id)
        expect(report[:summary]).to eq(
          total_actions: stats[:total_actions],
          unique_actions: stats[:unique_actions],
          engagement_score: user_score,
          first_activity: stats[:first_activity],
          last_activity: stats[:last_activity]
        )
      end

      it 'includes action_breakdown from stats' do
        report = reporter.generate_report(user_id)
        expect(report[:action_breakdown]).to eq(stats[:action_counts])
      end

      it 'formats patterns using format_pattern' do
        formatted_patterns = patterns.map do |p|
          {
            type: p['pattern_type'],
            description: p['description'],
            confidence: p['confidence']
          }
        end

        report = reporter.generate_report(user_id)
        expect(report[:patterns]).to eq(formatted_patterns)
      end

      it 'includes anomalies as returned by fetch_anomalies' do
        report = reporter.generate_report(user_id)
        expect(report[:anomalies]).to eq(anomalies)
      end

      it 'builds a timeline grouped by day by default' do
        expect(reporter).to receive(:format_timeline).with(activities, :day).and_call_original
        report = reporter.generate_report(user_id)
        expect(report[:timeline]).to be_an(Array)
        expect(report[:timeline].first).to include(:period, :total_actions, :actions, :first_timestamp, :last_timestamp)
      end

      it 'passes custom group_by option to format_timeline' do
        expect(reporter).to receive(:format_timeline).with(activities, :hour).and_call_original
        reporter.generate_report(user_id, group_by: :hour)
      end

      it 'generates insights using generate_insights' do
        expect(reporter).to receive(:generate_insights).with(stats, patterns, user_score, anomalies).and_call_original
        report = reporter.generate_report(user_id)
        expect(report[:insights]).to be_an(Array)
        expect(report[:insights]).not_to be_empty
      end
    end

    context 'when no activities are found' do
      before do
        allow(reporter).to receive(:fetch_user_activities).with(user_id).and_return([])
        allow(reporter).to receive(:error_report).and_call_original
      end

      it 'returns an error report' do
        report = reporter.generate_report(user_id)
        expect(report[:error]).to eq(true)
        expect(report[:message]).to eq('No activities found')
        expect(report).to have_key(:generated_at)
      end

      it 'does not call other fetch methods' do
        expect(reporter).not_to receive(:fetch_activity_stats)
        expect(reporter).not_to receive(:fetch_activity_patterns)
        expect(reporter).not_to receive(:fetch_user_score)
        expect(reporter).not_to receive(:fetch_anomalies)

        reporter.generate_report(user_id)
      end
    end
  end

  describe '#format_timeline' do
    context 'when activities array is empty' do
      it 'returns an empty array' do
        result = reporter.format_timeline([])
        expect(result).to eq([])
      end
    end

    context 'when grouping by day' do
      it 'groups activities by date and sorts by period' do
        result = reporter.format_timeline(activities, :day)

        expect(result.size).to eq(2)
        expect(result.map { |r| r[:period] }).to eq(['2024-01-01', '2024-01-02'])

        first_day = result.first
        expect(first_day[:total_actions]).to eq(2)
        expect(first_day[:actions]).to eq('login' => 1, 'click' => 1)
        expect(first_day[:first_timestamp]).to eq('2024-01-01T10:15:00Z')
        expect(first_day[:last_timestamp]).to eq('2024-01-01T11:00:00Z')
      end
    end

    context 'when grouping by hour' do
      it 'groups activities by hour' do
        result = reporter.format_timeline(activities, :hour)

        expect(result.map { |r| r[:period] }).to include('2024-01-01 10:00', '2024-01-01 11:00', '2024-01-02 09:00', '2024-01-02 10:00')
        hour_entry = result.find { |r| r[:period] == '2024-01-01 10:00' }
        expect(hour_entry[:total_actions]).to eq(1)
        expect(hour_entry[:actions]).to eq('login' => 1)
      end
    end

    context 'when grouping by week' do
      it 'groups activities by ISO week' do
        result = reporter.format_timeline(activities, :week)
        expect(result.size).to eq(1)
        expect(result.first[:period]).to match(/\A2024-W\d{2}\z/)
      end
    end

    context 'when grouping by month' do
      it 'groups activities by month' do
        result = reporter.format_timeline(activities, :month)
        expect(result.size).to eq(1)
        expect(result.first[:period]).to eq('2024-01')
      end
    end

    context 'when grouping by unknown key' do
      it 'defaults to grouping by day' do
        result = reporter.format_timeline(activities, :unknown)
        expect(result.map { |r| r[:period] }).to eq(['2024-01-01', '2024-01-02'])
      end
    end

    context 'when timestamps are invalid' do
      let(:bad_activities) do
        [
          { 'timestamp' => 'not-a-time', 'action' => 'login' }
        ]
      end

      it 'falls back to current time via parse_timestamp' do
        allow(Time).to receive(:now).and_return(Time.parse('2024-02-01T00:00:00Z'))
        result = reporter.format_timeline(bad_activities, :day)
        expect(result.first[:period]).to eq('2024-02-01')
      end
    end
  end

  describe '#export_to_json' do
    let(:report_hash) do
      {
        user_id: user_id,
        summary: { total_actions: 1 }
      }
    end

    before do
      allow(JSON).to receive(:pretty_generate).and_call_original
    end

    context 'when filepath is nil' do
      it 'returns success with data key containing JSON string' do
        result = reporter.export_to_json(report_hash)

        expect(result[:success]).to eq(true)
        expect(result[:data]).to be_a(String)
        parsed = JSON.parse(result[:data])
        expect(parsed['user_id']).to eq(user_id)
      end
    end

    context 'when filepath is provided' do
      let(:filepath) { File.join(Dir.tmpdir, "activity_report_#{Time.now.to_i}.json") }

      after do
        File.delete(filepath) if File.exist?(filepath)
      end

      it 'writes JSON to the file and returns metadata' do
        result = reporter.export_to_json(report_hash, filepath)

        expect(result[:success]).to eq(true)
        expect(result[:filepath]).to eq(filepath)
        expect(result[:size]).to be > 0
        expect(File).to exist(filepath)

        file_content = File.read(filepath)
        parsed = JSON.parse(file_content)
        expect(parsed['user_id']).to eq(user_id)
      end
    end

    context 'when an error occurs during file write' do
      let(:filepath) { '/root/forbidden_path.json' }

      it 'returns success: false with error message' do
        allow(File).to receive(:write).and_raise(StandardError.new('disk full'))

        result = reporter.export_to_json(report_hash, filepath)

        expect(result[:success]).to eq(false)
        expect(result[:error]).to eq('disk full')
      end
    end
  end

  describe '#compare_users' do
    let(:user_ids) { %w[user1 user2 user3] }

    let(:activities_user1) do
      [
        { 'timestamp' => '2024-01-01T10:00:00Z', 'action' => 'login' }
      ]
    end

    let(:activities_user2) do
      [
        { 'timestamp' => '2024-01-01T11:00:00Z', 'action' => 'login' },
        { 'timestamp' => '2024-01-01T12:00:00Z', 'action' => 'click' }
      ]
    end

    let(:activities_user3) do
      [
        { 'timestamp' => '2024-01-01T13:00:00Z', 'action' => 'login' },
        { 'timestamp' => '2024-01-01T14:00:00Z', 'action' => 'click' },
        { 'timestamp' => '2024-01-01T15:00:00Z', 'action' => 'purchase' }
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
        unique_actions: 2,
        action_counts: { 'login' => 1, 'click' => 1 },
        first_activity: '2024-01-01T11:00:00Z',
        last_activity: '2024-01-01T12:00:00Z',
        most_frequent: 'login'
      }
    end

    let(:stats_user3) do
      {
        total_actions: 3,
        unique_actions: 3,
        action_counts: { 'login' => 1, 'click' => 1, 'purchase' => 1 },
        first_activity: '2024-01-01T13:00:00Z',
        last_activity: '2024-01-01T15:00:00Z',
        most_frequent: 'login'
      }
    end

    before do
      allow(reporter).to receive(:fetch_user_activities).with('user1').and_return(activities_user1)
      allow(reporter).to receive(:fetch_user_activities).with('user2').and_return(activities_user2)
      allow(reporter).to receive(:fetch_user_activities).with('user3').and_return(activities_user3)

      allow(reporter).to receive(:fetch_activity_stats).with('user1').and_return(stats_user1)
      allow(reporter).to receive(:fetch_activity_stats).with('user2').and_return(stats_user2)
      allow(reporter).to receive(:fetch_activity_stats).with('user3').and_return(stats_user3)

      allow(reporter).to receive(:fetch_user_score).with(activities_user1).and_return(10.0)
      allow(reporter).to receive(:fetch_user_score).with(activities_user2).and_return(50.0)
      allow(reporter).to receive(:fetch_user_score).with(activities_user3).and_return(90.0)
    end

    context 'when fewer than 2 users are provided' do
      it 'returns an error report' do
        result = reporter.compare_users(['only-one'])

        expect(result[:error]).to eq(true)
        expect(result[:message]).to eq('At least 2 users required')
        expect(result).to have_key(:generated_at)
      end
    end

    context 'when 2 or more users are provided' do
      it 'returns comparison data with total_users and comparisons' do
        result = reporter.compare_users(user_ids)

        expect(result[:total_users]).to eq(3)
        expect(result[:comparisons]).to be_an(Array)
        expect(result[:comparisons].size).to eq(3)
      end

      it 'includes per-user comparison entries with expected fields' do
        result = reporter.compare_users(user_ids)
        entry = result[:comparisons].find { |c| c[:user_id] == 'user2' }

        expect(entry).to include(
          user_id: 'user2',
          total_actions: 2,
          engagement_score: 50.0,
          most_frequent_action: 'login'
        )
      end

      it 'sorts comparisons by engagement_score descending' do
        result = reporter.compare_users(user_ids)
        scores = result[:comparisons].map { |c| c[:engagement_score] }
        expect(scores).to eq(scores.sort.reverse)
      end

      it 'sets top_user to the user with highest engagement_score' do
        result = reporter.compare_users(user_ids)
        expect(result[:top_user]).to eq('user3')
      end

      it 'calculates average_score correctly' do
        result = reporter.compare_users(user_ids)
        expected_average = ((10.0 + 50.0 + 90.0) / 3.0).round(2)
        expect(result[:average_score]).to eq(expected_average)
      end
    end
  end

  describe '#format_pattern' do
    let(:pattern) do
      {
        'pattern_type' => 'night_owl',
        'description' => 'Active mostly at night',
        'confidence' => 0.7
      }
    end

    it 'returns a hash with type, description, and confidence' do
      result = reporter.send(:format_pattern, pattern)

      expect(result).to eq(
        type: 'night_owl',
        description: 'Active mostly at night',
        confidence: 0.7
      )
    end
  end

  describe '#generate_insights' do
    let(:base_stats) do
      {
        total_actions: 10,
        unique_actions: 3
      }
    end

    let(:no_patterns) { [] }
    let(:some_patterns) { [{}, {}, {}] }
    let(:no_anomalies) { [] }
    let(:some_anomalies) { [{}, {}] }

    context 'when user_score is high' do
      it 'includes highly engaged insight' do
        insights = reporter.send(:generate_insights, base_stats, no_patterns, 80.0, no_anomalies)
        expect(insights).to include('Highly engaged user with strong activity patterns')
      end
    end

    context 'when user_score is moderate' do
      it 'includes moderately engaged insight' do
        insights = reporter.send(:generate_insights, base_stats, no_patterns, 60.0, no_anomalies)
        expect(insights).to include('Moderately engaged user with regular activity')
      end
    end

    context 'when user_score is low' do
      it 'includes low engagement insight' do
        insights = reporter.send(:generate_insights, base_stats, no_patterns, 40.0, no_anomalies)
        expect(insights).to include('Low engagement - consider re-engagement strategies')
      end
    end

    context 'when unique_actions is greater than 10' do
      it 'includes diverse activity profile insight' do
        stats = base_stats.merge(unique_actions: 11)
        insights = reporter.send(:generate_insights, stats, no_patterns, 40.0, no_anomalies)
        expect(insights).to include('Diverse activity profile across multiple action types')
      end
    end

    context 'when more than 2 patterns exist' do
      it 'includes behavioral patterns detected insight' do
        insights = reporter.send(:generate_insights, base_stats, some_patterns, 40.0, no_anomalies)
        expect(insights).to include('Clear behavioral patterns detected')
      end
    end

    context 'when anomalies exist' do
      it 'includes anomalous activities insight with count' do
        insights = reporter.send(:generate_insights, base_stats, no_patterns, 40.0, some_anomalies)
        expect(insights).to include('2 anomalous activities detected - review recommended')
      end
    end

    context 'when total_actions is greater than 100' do
      it 'includes power user insight' do
        stats = base_stats.merge(total_actions: 150)
        insights = reporter.send(:generate_insights, stats, no_patterns, 40.0, no_anomalies)
        expect(insights).to include('Power user - high volume of activities')
      end
    end
  end

  describe '#parse_timestamp' do
    context 'with a valid timestamp string' do
      it 'parses and returns a Time object' do
        time = reporter.send(:parse_timestamp, '2024-01-01T10:00:00Z')
        expect(time).to be_a(Time)
        expect(time.utc.iso8601).to eq('2024-01-01T10:00:00Z')
      end
    end

    context 'with an invalid timestamp string' do
      it 'returns current time when parsing fails' do
        allow(Time).to receive(:now).and_return(Time.parse('2024-03-01T00:00:00Z'))
        time = reporter.send(:parse_timestamp, 'not-a-time')
        expect(time.utc.iso8601).to eq('2024-03-01T00:00:00Z')
      end
    end
  end

  describe '#error_report' do
    it 'returns an error hash with message and generated_at' do
      allow(Time).to receive(:now).and_return(Time.parse('2024-04-01T00:00:00Z'))
      result = reporter.send(:error_report, 'Something went wrong')

      expect(result[:error]).to eq(true)
      expect(result[:message]).to eq('Something went wrong')
      expect(result[:generated_at]).to eq('2024-04-01T00:00:00Z')
    end
  end
end
