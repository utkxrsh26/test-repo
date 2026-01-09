package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestReadConfig_TableDriven(t *testing.T) {
	type wantStruct struct {
		hasKey   bool
		keyValue interface{}
		isNil    bool
	}
	tests := []struct {
		name        string
		setupFile   func(t *testing.T) string
		expectPanic bool
		want        wantStruct
	}{
		{
			name: "valid JSON file returns parsed map",
			setupFile: func(t *testing.T) string {
				t.Helper()
				dir := t.TempDir()
				path := filepath.Join(dir, "config.json")
				content := map[string]interface{}{
					"port": float64(8080),
					"name": "app",
				}
				data, err := json.Marshal(content)
				assert.NoError(t, err)
				err = os.WriteFile(path, data, 0644)
				assert.NoError(t, err)
				return path
			},
			expectPanic: false,
			want: wantStruct{
				hasKey:   true,
				keyValue: float64(8080),
				isNil:    false,
			},
		},
		{
			name: "nonexistent file returns nil map due to read error",
			setupFile: func(t *testing.T) string {
				t.Helper()
				dir := t.TempDir()
				return filepath.Join(dir, "does_not_exist.json")
			},
			expectPanic: false,
			want: wantStruct{
				hasKey:   false,
				keyValue: nil,
				isNil:    true,
			},
		},
		{
			name: "invalid JSON returns nil map due to unmarshal error",
			setupFile: func(t *testing.T) string {
				t.Helper()
				dir := t.TempDir()
				path := filepath.Join(dir, "bad.json")
				err := os.WriteFile(path, []byte("{invalid json"), 0644)
				assert.NoError(t, err)
				return path
			},
			expectPanic: false,
			want: wantStruct{
				hasKey:   false,
				keyValue: nil,
				isNil:    true,
			},
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			path := tt.setupFile(t)
			defer func() {
				if r := recover(); r != nil {
					assert.True(t, tt.expectPanic, "unexpected panic: %v", r)
				} else {
					assert.False(t, tt.expectPanic, "expected panic but none occurred")
				}
			}()
			got := ReadConfig(path)
			if tt.want.isNil {
				assert.Nil(t, got)
				return
			}
			assert.NotNil(t, got)
			if tt.want.hasKey {
				val, ok := got["port"]
				assert.True(t, ok)
				assert.Equal(t, tt.want.keyValue, val)
			}
		})
	}
}

func TestReadConfig_EmptyFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "empty.json")
	err := os.WriteFile(path, []byte(""), 0644)
	assert.NoError(t, err)

	defer func() {
		if r := recover(); r != nil {
			assert.Fail(t, "unexpected panic on empty file", "%v", r)
		}
	}()

	got := ReadConfig(path)
	assert.Nil(t, got)
}

func TestReadConfig_NonJSONContent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "text.txt")
	err := os.WriteFile(path, []byte("just some text"), 0644)
	assert.NoError(t, err)

	defer func() {
		if r := recover(); r != nil {
			assert.Fail(t, "unexpected panic on non-JSON content", "%v", r)
		}
	}()

	got := ReadConfig(path)
	assert.Nil(t, got)
}

func TestWriteLog_TableDriven(t *testing.T) {
	tests := []struct {
		name        string
		message     string
		expectPanic bool
	}{
		{
			name:        "write simple message",
			message:     "hello world",
			expectPanic: false,
		},
		{
			name:        "write empty message",
			message:     "",
			expectPanic: false,
		},
		{
			name:        "write long message",
			message:     "this is a very long log message used for testing purposes",
			expectPanic: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			defer func() {
				if r := recover(); r != nil {
					assert.True(t, tt.expectPanic, "unexpected panic: %v", r)
				} else {
					assert.False(t, tt.expectPanic, "expected panic but none occurred")
				}
			}()

			dir := t.TempDir()
			logPath := filepath.Join(dir, "app.log")

			origWd, err := os.Getwd()
			assert.NoError(t, err)

			err = os.Chdir(dir)
			assert.NoError(t, err)
			defer func() {
				_ = os.Chdir(origWd)
			}()

			WriteLog(tt.message)

			data, err := os.ReadFile(logPath)
			if err != nil {
				assert.Fail(t, "expected log file to exist", "error: %v", err)
				return
			}
			content := string(data)
			assert.Contains(t, content, tt.message)
		})
	}
}

func TestWriteLog_AppendsToExistingFile(t *testing.T) {
	dir := t.TempDir()
	logPath := filepath.Join(dir, "app.log")

	err := os.WriteFile(logPath, []byte("existing\n"), 0644)
	assert.NoError(t, err)

	origWd, err := os.Getwd()
	assert.NoError(t, err)

	err = os.Chdir(dir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWd)
	}()

	WriteLog("new entry")

	data, err := os.ReadFile(logPath)
	assert.NoError(t, err)
	content := string(data)
	assert.Contains(t, content, "existing")
	assert.Contains(t, content, "new entry")
}

func TestWriteLog_MultipleCalls(t *testing.T) {
	dir := t.TempDir()
	logPath := filepath.Join(dir, "app.log")

	origWd, err := os.Getwd()
	assert.NoError(t, err)

	err = os.Chdir(dir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWd)
	}()

	messages := []string{"first", "second", "third"}
	for _, msg := range messages {
		WriteLog(msg)
	}

	data, err := os.ReadFile(logPath)
	assert.NoError(t, err)
	content := string(data)
	for _, msg := range messages {
		assert.Contains(t, content, msg)
	}
}

func TestProcessData_TableDriven(t *testing.T) {
	tests := []struct {
		name        string
		input       string
		want        string
		expectPanic bool
	}{
		{
			name:        "non-empty input returns same string",
			input:       "data",
			want:        "data",
			expectPanic: false,
		},
		{
			name:        "another non-empty input",
			input:       "test",
			want:        "test",
			expectPanic: false,
		},
		{
			name:        "empty input panics",
			input:       "",
			want:        "",
			expectPanic: true,
		},
		{
			name:        "whitespace input does not panic",
			input:       " ",
			want:        " ",
			expectPanic: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			defer func() {
				r := recover()
				if tt.expectPanic {
					assert.NotNil(t, r, "expected panic but none occurred")
				} else {
					assert.Nil(t, r, "unexpected panic: %v", r)
				}
			}()

			got := ProcessData(tt.input)
			if !tt.expectPanic {
				assert.Equal(t, tt.want, got)
			}
		})
	}
}

func TestProcessData_RepeatedCalls(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	for _, in := range inputs {
		func(val string) {
			defer func() {
				r := recover()
				assert.Nil(t, r, "unexpected panic for input %q: %v", val, r)
			}()
			got := ProcessData(val)
			assert.Equal(t, val, got)
		}(in)
	}
}

func TestProcessData_EmptyInputPanicMessage(t *testing.T) {
	defer func() {
		r := recover()
		assert.NotNil(t, r)
		msg, ok := r.(string)
		assert.True(t, ok)
		assert.Equal(t, "empty input", msg)
	}()
	_ = ProcessData("")
}
