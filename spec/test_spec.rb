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
    let(:id) { 42 }
    let(:query) { "SELECT * FROM users WHERE id = #{id}" }

    before do
      stub_const('DB', Class.new)
    end

    context 'with a valid integer id' do
      it 'executes the expected SQL query via DB.execute' do
        expect(DB).to receive(:execute).with(query).and_return([{ 'id' => id }])
        result = user.find_user(id)
        expect(result).to eq([{ 'id' => id }])
      end
    end

    context 'with a string id' do
      let(:id) { '7' }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'passes the interpolated string id into the SQL query' do
        expect(DB).to receive(:execute).with(query).and_return([{ 'id' => 7 }])
        result = user.find_user(id)
        expect(result).to eq([{ 'id' => 7 }])
      end
    end

    context 'with a nil id' do
      let(:id) { nil }
      let(:query) { "SELECT * FROM users WHERE id = #{id}" }

      it 'still calls DB.execute with the interpolated nil value' do
        expect(DB).to receive(:execute).with(query).and_return([])
        result = user.find_user(id)
        expect(result).to eq([])
      end
    end

    context 'when DB.execute raises an error' do
      let(:db_error) { StandardError.new('DB failure') }

      it 'propagates the error' do
        expect(DB).to receive(:execute).with(query).and_raise(db_error)
        expect do
          user.find_user(id)
        end.to raise_error(StandardError, 'DB failure')
      end
    end
  end

  describe '#bad_method' do
    let(:user) { described_class.new('Charlie') }

    it 'returns the sum of x, y, and z' do
      expect(user.bad_method).to eq(6)
    end

    it 'always returns the same value regardless of instance state' do
      other_user = described_class.new('Dana')
      expect(user.bad_method).to eq(6)
      expect(other_user.bad_method).to eq(6)
    end
  end
end
