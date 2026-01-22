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
      double('User', id: 1, name: 'Alice', posts: posts1)
    end

    let(:user2) do
      double('User', id: 2, name: 'Bob', posts: posts2)
    end

    let(:posts1) do
      double('PostsRelation1', count: 3)
    end

    let(:posts2) do
      double('PostsRelation2', count: 5)
    end

    before do
      allow(User).to receive(:find).with(1).and_return(user1)
      allow(User).to receive(:find).with(2).and_return(user2)
      allow_any_instance_of(ReportGenerator).to receive(:puts)
    end

    context 'with valid user_ids' do
      it 'queries each user by id' do
        report_generator.generate_user_report(user_ids)
        expect(User).to have_received(:find).with(1)
        expect(User).to have_received(:find).with(2)
      end

      it 'accesses posts for each user' do
        expect(user1).to receive(:posts).and_return(posts1)
        expect(user2).to receive(:posts).and_return(posts2)
        report_generator.generate_user_report(user_ids)
      end

      it 'prints a line for each user with post count' do
        expect(report_generator).to receive(:puts).with('Alice: 3 posts')
        expect(report_generator).to receive(:puts).with('Bob: 5 posts')
        report_generator.generate_user_report(user_ids)
      end
    end

    context 'with empty user_ids' do
      let(:user_ids) do
        []
      end

      it 'does not query any users' do
        report_generator.generate_user_report(user_ids)
        expect(User).not_to have_received(:find)
      end

      it 'does not print anything' do
        expect(report_generator).not_to receive(:puts)
        report_generator.generate_user_report(user_ids)
      end
    end

    context 'when User.find raises an error' do
      before do
        allow(User).to receive(:find).with(1).and_raise(ActiveRecord::RecordNotFound)
      end

      it 'propagates the error' do
        expect do
          report_generator.generate_user_report([1])
        end.to raise_error(ActiveRecord::RecordNotFound)
      end
    end
  end

  describe '#build_csv' do
    let(:record1) do
      double('Record', id: 1, name: 'Alice')
    end

    let(:record2) do
      double('Record', id: 2, name: 'Bob')
    end

    let(:records) do
      [record1, record2]
    end

    context 'with multiple records' do
      it 'returns a CSV string with one line per record' do
        result = report_generator.build_csv(records)
        expect(result).to eq("1,Alice\n2,Bob\n")
      end
    end

    context 'with a single record' do
      let(:records) do
        [record1]
      end

      it 'returns CSV with only that record' do
        result = report_generator.build_csv(records)
        expect(result).to eq("1,Alice\n")
      end
    end

    context 'with empty records' do
      let(:records) do
        []
      end

      it 'returns an empty string' do
        result = report_generator.build_csv(records)
        expect(result).to eq('')
      end
    end

    context 'with records having nil attributes' do
      let(:record_with_nil) do
        double('Record', id: nil, name: nil)
      end

      let(:records) do
        [record_with_nil]
      end

      it 'includes nil values converted to empty strings in interpolation' do
        result = report_generator.build_csv(records)
        expect(result).to eq(",\n")
      end
    end

    context 'with non-enumerable argument' do
      it 'raises a NoMethodError when each is not defined' do
        expect do
          report_generator.build_csv(nil)
        end.to raise_error(NoMethodError)
      end
    end
  end

  describe '#find_matches' do
    context 'with overlapping lists' do
      let(:list_a) do
        [1, 2, 3]
      end

      let(:list_b) do
        [2, 3, 4]
      end

      it 'returns elements present in both lists' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to match_array([2, 3])
      end
    end

    context 'with duplicate matches' do
      let(:list_a) do
        [1, 2, 2, 3]
      end

      let(:list_b) do
        [2, 2, 4]
      end

      it 'includes duplicates for each matching pair' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq([2, 2, 2, 2])
      end
    end

    context 'with no matches' do
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

    context 'with one empty list' do
      it 'returns empty when list_a is empty' do
        result = report_generator.find_matches([], [1, 2, 3])
        expect(result).to eq([])
      end

      it 'returns empty when list_b is empty' do
        result = report_generator.find_matches([1, 2, 3], [])
        expect(result).to eq([])
      end
    end

    context 'with both lists empty' do
      it 'returns an empty array' do
        result = report_generator.find_matches([], [])
        expect(result).to eq([])
      end
    end

    context 'with non-enumerable arguments' do
      it 'raises NoMethodError when list_a is invalid' do
        expect do
          report_generator.find_matches(nil, [1, 2])
        end.to raise_error(NoMethodError)
      end

      it 'raises NoMethodError when list_b is invalid' do
        expect do
          report_generator.find_matches([1, 2], nil)
        end.to raise_error(NoMethodError)
      end
    end
  end

  describe '#process_all_users' do
    let(:user1) do
      double('User', id: 1)
    end

    let(:user2) do
      double('User', id: 2)
    end

    let(:users_relation) do
      [user1, user2]
    end

    before do
      allow(User).to receive(:all).and_return(users_relation)
      allow(report_generator).to receive(:send_email)
    end

    context 'with users present' do
      it 'loads all users and sends an email to each' do
        report_generator.process_all_users
        expect(User).to have_received(:all)
        expect(report_generator).to have_received(:send_email).with(user1)
        expect(report_generator).to have_received(:send_email).with(user2)
      end
    end

    context 'when there are no users' do
      let(:users_relation) do
        []
      end

      it 'does not call send_email' do
        report_generator.process_all_users
        expect(report_generator).not_to have_received(:send_email)
      end
    end

    context 'when sending email fails for a user' do
      before do
        allow(report_generator).to receive(:send_email).with(user1).and_raise(StandardError.new('email failed'))
      end

      it 'propagates the error and stops processing' do
        expect do
          report_generator.process_all_users
        end.to raise_error(StandardError, 'email failed')
      end
    end

    context 'when User.all raises an error' do
      before do
        allow(User).to receive(:all).and_raise(StandardError.new('db error'))
      end

      it 'propagates the error' do
        expect do
          report_generator.process_all_users
        end.to raise_error(StandardError, 'db error')
      end
    end
  end
end
