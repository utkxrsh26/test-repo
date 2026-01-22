package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestReadConfig_TableDriven(t *testing.T) {
	tmpDir := t.TempDir()

	validPath := filepath.Join(tmpDir, "valid.json")
	validContent := `{"key":"value","number":42}`
	err := os.WriteFile(validPath, []byte(validContent), 0o644)
	assert.NoError(t, err)

	invalidJSONPath := filepath.Join(tmpDir, "invalid.json")
	invalidContent := `{"key": "value",`
	err = os.WriteFile(invalidJSONPath, []byte(invalidContent), 0o644)
	assert.NoError(t, err)

	tests := []struct {
		name        string
		path        string
		expectEmpty bool
	}{
		{
			name:        "nonexistent file returns empty map",
			path:        filepath.Join(tmpDir, "does-not-exist.json"),
			expectEmpty: true,
		},
		{
			name:        "valid json file returns parsed map",
			path:        validPath,
			expectEmpty: false,
		},
		{
			name:        "invalid json returns empty map",
			path:        invalidJSONPath,
			expectEmpty: true,
		},
		{
			name:        "empty path returns empty map",
			path:        "",
			expectEmpty: true,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			cfg := ReadConfig(tt.path)
			assert.NotNil(t, cfg)

			if tt.expectEmpty {
				assert.Equal(t, 0, len(cfg))
				return
			}

			assert.Equal(t, 2, len(cfg))
			assert.Equal(t, "value", cfg["key"])

			numberVal, ok := cfg["number"]
			assert.True(t, ok)

			switch v := numberVal.(type) {
			case float64:
				assert.Equal(t, float64(42), v)
			case json.Number:
				n, err := v.Int64()
				assert.NoError(t, err)
				assert.Equal(t, int64(42), n)
			default:
				assert.Fail(t, "unexpected type for number field")
			}
		})
	}
}

func TestReadConfig_MultipleCallsIndependence(t *testing.T) {
	tmpDir := t.TempDir()

	path1 := filepath.Join(tmpDir, "cfg1.json")
	path2 := filepath.Join(tmpDir, "cfg2.json")

	err := os.WriteFile(path1, []byte(`{"a":1}`), 0o644)
	assert.NoError(t, err)
	err = os.WriteFile(path2, []byte(`{"b":2}`), 0o644)
	assert.NoError(t, err)

	cfg1 := ReadConfig(path1)
	cfg2 := ReadConfig(path2)

	assert.NotNil(t, cfg1)
	assert.NotNil(t, cfg2)

	assert.Equal(t, 1, len(cfg1))
	assert.Equal(t, 1, len(cfg2))

	_, ok1 := cfg1["a"]
	_, ok2 := cfg2["b"]
	assert.True(t, ok1)
	assert.True(t, ok2)
}

func TestWriteLog_TableDriven(t *testing.T) {
	tmpDir := t.TempDir()

	readOnlyDir := filepath.Join(tmpDir, "readonly")
	err := os.Mkdir(readOnlyDir, 0o500)
	assert.NoError(t, err)

	readOnlyFile := filepath.Join(readOnlyDir, "app.log")
	f, err := os.OpenFile(readOnlyFile, os.O_CREATE|os.O_WRONLY, 0o400)
	assert.NoError(t, err)
	assert.NoError(t, f.Close())

	origWD, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	tests := []struct {
		name           string
		setup          func(t *testing.T)
		expectFile     bool
		expectContains string
	}{
		{
			name: "creates log file and writes message",
			setup: func(t *testing.T) {
				_ = os.Remove("app.log")
			},
			expectFile:     true,
			expectContains: "hello world",
		},
		{
			name: "appends to existing log file",
			setup: func(t *testing.T) {
				err := os.WriteFile("app.log", []byte("existing\n"), 0o644)
				assert.NoError(t, err)
			},
			expectFile:     true,
			expectContains: "second message",
		},
		{
			name: "write when directory is read-only (still uses current dir app.log)",
			setup: func(t *testing.T) {
				_ = os.Remove("app.log")
			},
			expectFile:     true,
			expectContains: "readonly test",
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			tt.setup(t)

			switch tt.name {
			case "creates log file and writes message":
				WriteLog("hello world")
			case "appends to existing log file":
				WriteLog("second message")
			case "write when directory is read-only (still uses current dir app.log)":
				WriteLog("readonly test")
			}

			_, err := os.Stat("app.log")
			if tt.expectFile {
				assert.NoError(t, err)
				data, err := os.ReadFile("app.log")
				assert.NoError(t, err)
				assert.Contains(t, string(data), tt.expectContains)
			} else {
				assert.Error(t, err)
			}
		})
	}
}

func TestWriteLog_MultipleSequentialWrites(t *testing.T) {
	tmpDir := t.TempDir()

	origWD, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	messages := []string{"first\n", "second\n", "third\n"}

	for _, msg := range messages {
		WriteLog(msg)
	}

	data, err := os.ReadFile("app.log")
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
		expectPanic bool
	}{
		{
			name:        "non-empty input returns same string",
			input:       "some data",
			expectPanic: false,
		},
		{
			name:        "whitespace input returns same string",
			input:       "   ",
			expectPanic: false,
		},
		{
			name:        "empty input panics",
			input:       "",
			expectPanic: true,
		},
		{
			name:        "long input returns same string",
			input:       "this is a longer input string to verify behavior",
			expectPanic: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			if tt.expectPanic {
				defer func() {
					r := recover()
					assert.NotNil(t, r)
					if r != nil {
						if msg, ok := r.(string); ok {
							assert.Equal(t, "empty input", msg)
						}
					}
				}()
				_ = ProcessData(tt.input)
				return
			}

			defer func() {
				r := recover()
				assert.Nil(t, r)
			}()

			got := ProcessData(tt.input)
			assert.Equal(t, tt.input, got)
		})
	}
}

func TestProcessData_IdempotentForSameInput(t *testing.T) {
	input := "repeatable input"

	first := ProcessData(input)
	second := ProcessData(input)

	assert.Equal(t, input, first)
	assert.Equal(t, input, second)
	assert.Equal(t, first, second)
}
