require 'spec_helper'
require_relative '../test'

RSpec.describe User do
  let(:name) { 'Alice' }
  let(:user) { described_class.new(name) }

  describe '#initialize' do
    it 'creates a User instance with the given name' do
      expect(user).to be_a(described_class)
    end

    context 'when name is nil' do
      let(:name) { nil }

      it 'still creates a User instance' do
        expect(user).to be_a(described_class)
      end
    end

    context 'when name is an empty string' do
      let(:name) { '' }

      it 'still creates a User instance' do
        expect(user).to be_a(described_class)
      end
    end
  end

  describe '#find_user' do
    let(:db_double) { class_double('DB') }

    before do
      stub_const('DB', db_double)
    end

    context 'with a valid integer id' do
      let(:id) { 1 }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:db_result) { [{ 'id' => 1, 'name' => 'Alice' }] }

      it 'executes the correct SQL query and returns the result' do
        expect(DB).to receive(:execute).with(expected_query).and_return(db_result)
        result = user.find_user(id)
        expect(result).to eq(db_result)
      end
    end

    context 'with a string id' do
      let(:id) { '2' }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:db_result) { [{ 'id' => 2, 'name' => 'Bob' }] }

      it 'interpolates the id into the SQL query as a string' do
        expect(DB).to receive(:execute).with(expected_query).and_return(db_result)
        result = user.find_user(id)
        expect(result).to eq(db_result)
      end
    end

    context 'with a nil id' do
      let(:id) { nil }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:db_result) { [] }

      it 'builds a query with nil and returns the DB result' do
        expect(DB).to receive(:execute).with(expected_query).and_return(db_result)
        result = user.find_user(id)
        expect(result).to eq(db_result)
      end
    end

    context 'when DB.execute raises an error' do
      let(:id) { 3 }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:db_error) { StandardError.new('DB failure') }

      it 'propagates the error' do
        expect(DB).to receive(:execute).with(expected_query).and_raise(db_error)
        expect do
          user.find_user(id)
        end.to raise_error(StandardError, 'DB failure')
      end
    end
  end

  describe '#bad_method' do
    it 'returns the sum of internal variables' do
      expect(user.bad_method).to eq(6)
    end

    context 'when called multiple times' do
      it 'returns the same result each time' do
        first_call = user.bad_method
        second_call = user.bad_method
        expect(first_call).to eq(6)
        expect(second_call).to eq(6)
      end
    end
  end
end
