require 'spec_helper'
require 'rails_helper'
require_relative '../test_performance'

RSpec.describe ReportGenerator do
  let(:report_generator) do
    described_class.new
  end

  describe '#generate_user_report' do
    let(:user_ids) do
      [1, 2]
    end

    let(:user1) do
      instance_double('User', name: 'Alice', posts: posts1)
    end

    let(:user2) do
      instance_double('User', name: 'Bob', posts: posts2)
    end

    let(:posts1) do
      instance_double('ActiveRecord::Relation', count: 3)
    end

    let(:posts2) do
      instance_double('ActiveRecord::Relation', count: 5)
    end

    before do
      allow(User).to receive(:find).with(1).and_return(user1)
      allow(User).to receive(:find).with(2).and_return(user2)
    end

    context 'with valid user_ids' do
      it 'queries each user and their posts' do
        expect(User).to receive(:find).with(1).ordered.and_return(user1)
        expect(User).to receive(:find).with(2).ordered.and_return(user2)
        expect(user1).to receive(:posts).and_return(posts1)
        expect(user2).to receive(:posts).and_return(posts2)

        expect do
          report_generator.generate_user_report(user_ids)
        end.to output("Alice: 3 posts\nBob: 5 posts\n").to_stdout
      end
    end

    context 'when user_ids is empty' do
      let(:user_ids) do
        []
      end

      it 'does not query any users and outputs nothing' do
        expect(User).not_to receive(:find)

        expect do
          report_generator.generate_user_report(user_ids)
        end.to output("").to_stdout
      end
    end

    context 'when User.find raises an error' do
      before do
        allow(User).to receive(:find).with(1).and_raise(StandardError.new('DB error'))
      end

      it 'propagates the error' do
        expect do
          report_generator.generate_user_report([1])
        end.to raise_error(StandardError, 'DB error')
      end
    end

    context 'when user has no posts' do
      let(:posts1) do
        instance_double('ActiveRecord::Relation', count: 0)
      end

      let(:user_ids) do
        [1]
      end

      it 'prints zero posts for that user' do
        expect do
          report_generator.generate_user_report(user_ids)
        end.to output("Alice: 0 posts\n").to_stdout
      end
    end
  end

  describe '#build_csv' do
    let(:record1) do
      instance_double('Record', id: 1, name: 'Alice')
    end

    let(:record2) do
      instance_double('Record', id: 2, name: 'Bob')
    end

    let(:records) do
      [record1, record2]
    end

    context 'with multiple records' do
      it 'builds a CSV string with each record on its own line' do
        result = report_generator.build_csv(records)
        expect(result).to eq("1,Alice\n2,Bob\n")
      end
    end

    context 'with a single record' do
      let(:records) do
        [record1]
      end

      it 'returns CSV with one line' do
        result = report_generator.build_csv(records)
        expect(result).to eq("1,Alice\n")
      end
    end

    context 'with no records' do
      let(:records) do
        []
      end

      it 'returns an empty string' do
        result = report_generator.build_csv(records)
        expect(result).to eq("")
      end
    end

    context 'when records contain nil values' do
      let(:record_with_nil_name) do
        instance_double('Record', id: 3, name: nil)
      end

      let(:records) do
        [record_with_nil_name]
      end

      it 'converts nil to empty string in CSV output' do
        result = report_generator.build_csv(records)
        expect(result).to eq("3,\n")
      end
    end

    context 'when records is nil' do
      let(:records) do
        nil
      end

      it 'raises NoMethodError due to calling each on nil' do
        expect do
          report_generator.build_csv(records)
        end.to raise_error(NoMethodError)
      end
    end
  end

  describe '#find_matches' do
    let(:list_a) do
      [1, 2, 3]
    end

    let(:list_b) do
      [2, 3, 4]
    end

    context 'with overlapping elements' do
      it 'returns all matching elements including duplicates from nested loops' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to contain_exactly(2, 3)
      end
    end

    context 'when lists have duplicate values' do
      let(:list_a) do
        [1, 2, 2]
      end

      let(:list_b) do
        [2, 2]
      end

      it 'includes duplicates for each matching pair' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq([2, 2, 2, 2])
      end
    end

    context 'when there are no matches' do
      let(:list_a) do
        [1, 5]
      end

      let(:list_b) do
        [2, 3, 4]
      end

      it 'returns an empty array' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq([])
      end
    end

    context 'when one list is empty' do
      let(:list_a) do
        []
      end

      it 'returns an empty array' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq([])
      end
    end

    context 'when both lists are empty' do
      let(:list_a) do
        []
      end

      let(:list_b) do
        []
      end

      it 'returns an empty array' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq([])
      end
    end

    context 'when lists contain non-numeric elements' do
      let(:list_a) do
        ['a', 'b', 'c']
      end

      let(:list_b) do
        ['b', 'd']
      end

      it 'matches based on equality' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq(['b'])
      end
    end

    context 'when list_a is nil' do
      let(:list_a) do
        nil
      end

      it 'raises NoMethodError due to calling each on nil' do
        expect do
          report_generator.find_matches(list_a, list_b)
        end.to raise_error(NoMethodError)
      end
    end
  end

  describe '#process_all_users' do
    let(:user1) do
      instance_double('User', id: 1)
    end

    let(:user2) do
      instance_double('User', id: 2)
    end

    let(:users_relation) do
      [user1, user2]
    end

    before do
      stub_const('User', Class.new)
      allow(User).to receive(:all).and_return(users_relation)
    end

    context 'with users present' do
      it 'iterates over all users and sends emails' do
        expect(report_generator).to receive(:send_email).with(user1).ordered
        expect(report_generator).to receive(:send_email).with(user2).ordered

        report_generator.process_all_users
      end
    end

    context 'when there are no users' do
      let(:users_relation) do
        []
      end

      it 'does not call send_email' do
        expect(report_generator).not_to receive(:send_email)

        report_generator.process_all_users
      end
    end

    context 'when sending email raises an error' do
      before do
        allow(report_generator).to receive(:send_email).with(user1).and_raise(StandardError.new('SMTP error'))
      end

      it 'propagates the error and stops processing' do
        expect do
          report_generator.process_all_users
        end.to raise_error(StandardError, 'SMTP error')
      end
    end

    context 'when User.all raises an error' do
      before do
        allow(User).to receive(:all).and_raise(StandardError.new('DB error'))
      end

      it 'propagates the error' do
        expect do
          report_generator.process_all_users
        end.to raise_error(StandardError, 'DB error')
      end
    end
  end
end
