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
      double('User', name: 'Alice', posts: double('PostsRelation1', count: 3))
    end

    let(:user2) do
      double('User', name: 'Bob', posts: double('PostsRelation2', count: 5))
    end

    before do
      allow(User).to receive(:find).with(1).and_return(user1)
      allow(User).to receive(:find).with(2).and_return(user2)
    end

    context 'with valid user ids' do
      it 'queries each user and their posts and prints the report lines' do
        expect(User).to receive(:find).with(1).once.and_return(user1)
        expect(User).to receive(:find).with(2).once.and_return(user2)

        expect(user1).to receive(:posts).and_return(user1.posts)
        expect(user2).to receive(:posts).and_return(user2.posts)

        expect(user1.posts).to receive(:count).and_return(3)
        expect(user2.posts).to receive(:count).and_return(5)

        expect do
          report_generator.generate_user_report(user_ids)
        end.to output("Alice: 3 posts\nBob: 5 posts\n").to_stdout
      end
    end

    context 'with an empty array of user ids' do
      let(:user_ids) do
        []
      end

      it 'does not query any users and prints nothing' do
        expect(User).not_to receive(:find)

        expect do
          report_generator.generate_user_report(user_ids)
        end.to output("").to_stdout
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

    context 'when user has no posts' do
      let(:user_without_posts) do
        double('User', name: 'Charlie', posts: double('PostsRelation3', count: 0))
      end

      before do
        allow(User).to receive(:find).with(3).and_return(user_without_posts)
      end

      it 'prints zero posts for that user' do
        expect do
          report_generator.generate_user_report([3])
        end.to output("Charlie: 0 posts\n").to_stdout
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

    context 'with multiple records' do
      let(:records) do
        [record1, record2]
      end

      it 'builds a CSV string with one line per record' do
        result = report_generator.build_csv(records)
        expect(result).to eq("1,Alice\n2,Bob\n")
      end
    end

    context 'with a single record' do
      let(:records) do
        [record1]
      end

      it 'builds a CSV string with a single line' do
        result = report_generator.build_csv(records)
        expect(result).to eq("1,Alice\n")
      end
    end

    context 'with an empty array' do
      let(:records) do
        []
      end

      it 'returns an empty string' do
        result = report_generator.build_csv(records)
        expect(result).to eq("")
      end
    end

    context 'with records having nil attributes' do
      let(:record_with_nil) do
        double('Record', id: nil, name: nil)
      end

      let(:records) do
        [record_with_nil]
      end

      it 'includes nil values converted to empty strings via interpolation' do
        result = report_generator.build_csv(records)
        expect(result).to eq(",\n")
      end
    end

    context 'when records is nil' do
      it 'raises a NoMethodError when trying to iterate' do
        expect do
          report_generator.build_csv(nil)
        end.to raise_error(NoMethodError)
      end
    end
  end

  describe '#find_matches' do
    context 'with overlapping elements' do
      let(:list_a) do
        [1, 2, 3]
      end

      let(:list_b) do
        [2, 3, 4]
      end

      it 'returns all matching elements' do
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to match_array([2, 3])
      end

      it 'includes duplicates when elements appear multiple times' do
        list_a = [1, 2, 2, 3]
        list_b = [2, 2, 4]
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq([2, 2, 2, 2])
      end
    end

    context 'with no overlapping elements' do
      let(:list_a) do
        [1, 5, 6]
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
      it 'returns an empty array when list_a is empty' do
        result = report_generator.find_matches([], [1, 2, 3])
        expect(result).to eq([])
      end

      it 'returns an empty array when list_b is empty' do
        result = report_generator.find_matches([1, 2, 3], [])
        expect(result).to eq([])
      end
    end

    context 'when both lists are empty' do
      it 'returns an empty array' do
        result = report_generator.find_matches([], [])
        expect(result).to eq([])
      end
    end

    context 'with different data types' do
      it 'matches elements using == comparison' do
        list_a = ['1', :two, 3]
        list_b = ['1', 'two', 3.0]
        result = report_generator.find_matches(list_a, list_b)
        expect(result).to eq(['1', 3])
      end
    end

    context 'when list_a is nil' do
      it 'raises a NoMethodError when trying to iterate' do
        expect do
          report_generator.find_matches(nil, [1, 2])
        end.to raise_error(NoMethodError)
      end
    end

    context 'when list_b is nil' do
      it 'raises a NoMethodError when trying to iterate' do
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

    context 'when there are users returned by User.all' do
      it 'iterates over all users and sends an email to each' do
        expect(User).to receive(:all).and_return(users_relation)
        expect(report_generator).to receive(:send_email).with(user1).once
        expect(report_generator).to receive(:send_email).with(user2).once

        report_generator.process_all_users
      end
    end

    context 'when User.all returns an empty collection' do
      let(:users_relation) do
        []
      end

      it 'does not attempt to send any emails' do
        expect(User).to receive(:all).and_return(users_relation)
        expect(report_generator).not_to receive(:send_email)

        report_generator.process_all_users
      end
    end

    context 'when send_email raises an error for a user' do
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
