require 'spec_helper'
require_relative '../test'

RSpec.describe User do
  describe '#initialize' do
    let(:name) { 'Alice' }
    let(:user) { described_class.new(name) }

    it 'creates an instance of User' do
      expect(user).to be_a(described_class)
    end

    it 'sets the @name instance variable' do
      expect(user.instance_variable_get(:@name)).to eq(name)
    end

    context 'when name is nil' do
      let(:name) { nil }

      it 'allows name to be nil' do
        expect(user.instance_variable_get(:@name)).to be_nil
      end
    end

    context 'when name is an empty string' do
      let(:name) { '' }

      it 'sets name to empty string' do
        expect(user.instance_variable_get(:@name)).to eq('')
      end
    end
  end

  describe '#find_user' do
    let(:name) { 'Bob' }
    let(:user) { described_class.new(name) }
    let(:db_double) { class_double('DB') }

    before do
      stub_const('DB', db_double)
    end

    context 'with a valid integer id' do
      let(:id) { 1 }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:db_result) { [{ 'id' => 1, 'name' => 'Bob' }] }

      it 'executes the correct SQL query via DB.execute' do
        expect(DB).to receive(:execute).with(expected_query).and_return(db_result)
        result = user.find_user(id)
        expect(result).to eq(db_result)
      end
    end

    context 'with a string id' do
      let(:id) { '42' }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:db_result) { [{ 'id' => 42, 'name' => 'Bob' }] }

      it 'interpolates the string id into the SQL query' do
        expect(DB).to receive(:execute).with(expected_query).and_return(db_result)
        result = user.find_user(id)
        expect(result).to eq(db_result)
      end
    end

    context 'with a nil id' do
      let(:id) { nil }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'passes a query with nil interpolated to DB.execute' do
        expect(DB).to receive(:execute).with(expected_query).and_return(nil)
        result = user.find_user(id)
        expect(result).to be_nil
      end
    end

    context 'when DB.execute raises an error' do
      let(:id) { 99 }
      let(:expected_query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'propagates the error' do
        expect(DB).to receive(:execute).with(expected_query).and_raise(StandardError.new('DB failure'))
        expect do
          user.find_user(id)
        end.to raise_error(StandardError, 'DB failure')
      end
    end
  end

  describe '#bad_method' do
    let(:user) { described_class.new('Charlie') }

    it 'returns the sum of 1, 2, and 3' do
      expect(user.bad_method).to eq(6)
    end

    it 'always returns an Integer' do
      expect(user.bad_method).to be_a(Integer)
    end
  end
end
