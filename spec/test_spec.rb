require 'spec_helper'
require_relative '../test'

RSpec.describe User do
  describe '#initialize' do
    let(:name) { 'Alice' }
    let(:user) { described_class.new(name) }

    it 'creates an instance of User' do
      expect(user).to be_a(described_class)
    end

    it 'sets the name instance variable' do
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

      it 'stores the empty string as name' do
        expect(user.instance_variable_get(:@name)).to eq('')
      end
    end
  end

  describe '#find_user' do
    let(:name) { 'Bob' }
    let(:user) { described_class.new(name) }
    let(:id) { 1 }
    let(:query) { "SELECT * FROM users WHERE id = #{id}" }

    before do
      stub_const('DB', double('DB')) unless defined?(DB)
    end

    context 'with a valid integer id' do
      let(:id) { 42 }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:result) { [{ 'id' => 42, 'name' => 'Bob' }] }

      it 'executes the query with the interpolated id and returns the result' do
        expect(DB).to receive(:execute).with(query).and_return(result)
        expect(user.find_user(id)).to eq(result)
      end
    end

    context 'with id as a string' do
      let(:id) { '7' }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }
      let(:result) { [{ 'id' => 7, 'name' => 'String ID' }] }

      it 'passes the string directly into the query' do
        expect(DB).to receive(:execute).with(query).and_return(result)
        expect(user.find_user(id)).to eq(result)
      end
    end

    context 'when DB.execute raises an error' do
      let(:id) { 99 }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'propagates the error' do
        expect(DB).to receive(:execute).with(query).and_raise(StandardError.new('DB failure'))
        expect do
          user.find_user(id)
        end.to raise_error(StandardError, 'DB failure')
      end
    end

    context 'with a potentially dangerous id (SQL injection attempt)' do
      let(:id) { "1; DROP TABLE users;" }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'passes the raw id into the query string' do
        expect(DB).to receive(:execute).with(query)
        user.find_user(id)
      end
    end

    context 'with nil id' do
      let(:id) { nil }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'builds a query with nil and calls DB.execute' do
        expect(DB).to receive(:execute).with(query)
        user.find_user(id)
      end
    end
  end

  describe '#bad_method' do
    let(:name) { 'Charlie' }
    let(:user) { described_class.new(name) }

    it 'returns the sum of x, y, and z' do
      expect(user.bad_method).to eq(6)
    end

    it 'always returns an Integer' do
      expect(user.bad_method).to be_a(Integer)
    end

    context 'multiple calls' do
      it 'returns the same result each time' do
        first = user.bad_method
        second = user.bad_method
        expect(first).to eq(6)
        expect(second).to eq(6)
      end
    end
  end
end
