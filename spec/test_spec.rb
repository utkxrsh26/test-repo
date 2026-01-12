require 'spec_helper'
require_relative '../test'

RSpec.describe User do
  let(:name) { 'Alice' }
  let(:user) { described_class.new(name) }

  describe '#initialize' do
    it 'creates a User instance' do
      expect(user).to be_a(described_class)
    end

    it 'sets the name instance variable' do
      expect(user.instance_variable_get(:@name)).to eq(name)
    end

    context 'with nil name' do
      let(:name) { nil }

      it 'allows nil name' do
        expect(user.instance_variable_get(:@name)).to be_nil
      end
    end

    context 'with empty string name' do
      let(:name) { '' }

      it 'sets an empty string name' do
        expect(user.instance_variable_get(:@name)).to eq('')
      end
    end
  end

  describe '#find_user' do
    let(:db_double) { instance_double('DB') }
    let(:id) { 1 }
    let(:query) { "SELECT * FROM users WHERE id = #{id}" }
    let(:result) { [{ 'id' => id, 'name' => 'Alice' }] }

    before do
      stub_const('DB', db_double)
    end

    context 'with a valid integer id' do
      it 'executes the correct SQL query' do
        expect(DB).to receive(:execute).with(query).and_return(result)
        user.find_user(id)
      end

      it 'returns the result from DB.execute' do
        allow(DB).to receive(:execute).with(query).and_return(result)
        expect(user.find_user(id)).to eq(result)
      end
    end

    context 'with a string id' do
      let(:id) { '5' }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'passes the interpolated string id to the query' do
        expect(DB).to receive(:execute).with(query).and_return(result)
        user.find_user(id)
      end
    end

    context 'when DB.execute raises an error' do
      let(:db_error) { StandardError.new('DB failure') }

      it 'propagates the error' do
        allow(DB).to receive(:execute).and_raise(db_error)
        expect do
          user.find_user(id)
        end.to raise_error(StandardError, 'DB failure')
      end
    end

    context 'with nil id' do
      let(:id) { nil }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'still builds a query with nil and calls DB.execute' do
        expect(DB).to receive(:execute).with(query).and_return([])
        user.find_user(id)
      end
    end
  end

  describe '#bad_method' do
    it 'returns the sum of x, y, and z' do
      expect(user.bad_method).to eq(6)
    end

    it 'always returns the same value regardless of name' do
      other_user = described_class.new('Bob')
      expect(other_user.bad_method).to eq(6)
    end
  end
end
