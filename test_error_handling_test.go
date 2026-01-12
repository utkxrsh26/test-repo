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
	invalidContent := `{"key":`
	err = os.WriteFile(invalidJSONPath, []byte(invalidContent), 0o644)
	assert.NoError(t, err)

	tests := []struct {
		name        string
		path        string
		setup       func()
		expectNil   bool
		expectEmpty bool
	}{
		{
			name:      "valid JSON file returns parsed map",
			path:      validPath,
			setup:     func() {},
			expectNil: false,
		},
		{
			name:      "nonexistent file returns nil map due to read error",
			path:      filepath.Join(tmpDir, "does_not_exist.json"),
			setup:     func() {},
			expectNil: true,
		},
		{
			name:      "invalid JSON returns nil map due to unmarshal error",
			path:      invalidJSONPath,
			setup:     func() {},
			expectNil: true,
		},
		{
			name: "empty file returns nil map due to unmarshal error",
			path: filepath.Join(tmpDir, "empty.json"),
			setup: func() {
				_ = os.WriteFile(filepath.Join(tmpDir, "empty.json"), []byte(""), 0o644)
			},
			expectNil: true,
		},
		{
			name: "directory path returns nil map due to read error",
			path: tmpDir,
			setup: func() {
				// tmpDir already exists as directory
			},
			expectNil: true,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			tt.setup()
			got := ReadConfig(tt.path)

			if tt.expectNil {
				assert.Nil(t, got)
				return
			}

			assert.NotNil(t, got)
			if got == nil {
				return
			}

			if tt.path == validPath {
				assert.Equal(t, "value", got["key"])
				// json.Unmarshal decodes numbers as float64 by default
				num, ok := got["number"].(float64)
				assert.True(t, ok)
				if ok {
					assert.Equal(t, float64(42), num)
				}
			}
		})
	}
}

func TestReadConfig_MultipleCallsIndependence(t *testing.T) {
	tmpDir := t.TempDir()

	path1 := filepath.Join(tmpDir, "config1.json")
	path2 := filepath.Join(tmpDir, "config2.json")

	err := os.WriteFile(path1, []byte(`{"a":1}`), 0o644)
	assert.NoError(t, err)
	err = os.WriteFile(path2, []byte(`{"b":2}`), 0o644)
	assert.NoError(t, err)

	cfg1 := ReadConfig(path1)
	cfg2 := ReadConfig(path2)

	if assert.NotNil(t, cfg1) && assert.NotNil(t, cfg2) {
		_, hasA := cfg1["a"]
		_, hasB := cfg1["b"]
		assert.True(t, hasA)
		assert.False(t, hasB)

		_, hasA2 := cfg2["a"]
		_, hasB2 := cfg2["b"]
		assert.False(t, hasA2)
		assert.True(t, hasB2)
	}
}

func TestReadConfig_EmptyPath(t *testing.T) {
	cfg := ReadConfig("")
	assert.Nil(t, cfg)
}

func TestWriteLog_TableDriven(t *testing.T) {
	// Change working directory to temp dir so app.log is created there
	tmpDir := t.TempDir()
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	tests := []struct {
		name        string
		message     string
		expectExist bool
	}{
		{
			name:        "simple message creates log file",
			message:     "hello world",
			expectExist: true,
		},
		{
			name:        "empty message still creates log file",
			message:     "",
			expectExist: true,
		},
		{
			name:        "multiple writes append to same file",
			message:     "first",
			expectExist: true,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			WriteLog(tt.message)

			_, err := os.Stat("app.log")
			if tt.expectExist {
				assert.NoError(t, err)
			} else {
				assert.Error(t, err)
			}
		})
	}

	t.Run("content is appended without error checking", func(t *testing.T) {
		_ = os.Remove("app.log")

		WriteLog("line1\n")
		WriteLog("line2\n")

		data, err := os.ReadFile("app.log")
		assert.NoError(t, err)

		content := string(data)
		assert.Contains(t, content, "line1")
		assert.Contains(t, content, "line2")
	})
}

func TestWriteLog_FilePermissionsAndReuse(t *testing.T) {
	tmpDir := t.TempDir()
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	// Pre-create app.log with specific permissions
	err = os.WriteFile("app.log", []byte("existing\n"), 0o600)
	assert.NoError(t, err)

	WriteLog("new entry\n")

	data, err := os.ReadFile("app.log")
	assert.NoError(t, err)
	content := string(data)
	assert.Contains(t, content, "existing")
	assert.Contains(t, content, "new entry")
}

func TestProcessData_TableDriven(t *testing.T) {
	tests := []struct {
		name      string
		input     string
		want      string
		wantPanic bool
	}{
		{
			name:      "non-empty input returns same string",
			input:     "data",
			want:      "data",
			wantPanic: false,
		},
		{
			name:      "whitespace string is treated as non-empty",
			input:     " ",
			want:      " ",
			wantPanic: false,
		},
		{
			name:      "empty string panics",
			input:     "",
			want:      "",
			wantPanic: true,
		},
		{
			name:      "long string returns same value",
			input:     "this is a long string for testing",
			want:      "this is a long string for testing",
			wantPanic: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			if tt.wantPanic {
				assert.Panics(t, func() {
					_ = ProcessData(tt.input)
				})
				return
			}

			assert.NotPanics(t, func() {
				got := ProcessData(tt.input)
				assert.Equal(t, tt.want, got)
			})
		})
	}
}

func TestProcessData_PanicMessage(t *testing.T) {
	defer func() {
		r := recover()
		assert.NotNil(t, r)
		if r == nil {
			return
		}
		msg, ok := r.(string)
		if ok {
			assert.Equal(t, "empty input", msg)
		}
	}()

	_ = ProcessData("")
}

func TestProcessData_MultipleSequentialCalls(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	results := make([]string, 0, len(inputs))

	for _, in := range inputs {
		out := ProcessData(in)
		results = append(results, out)
	}

	assert.Equal(t, inputs, results)
}

func TestReadConfig_ReturnTypeIsMapStringInterface(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "config.json")
	err := os.WriteFile(path, []byte(`{"x":1}`), 0o644)
	assert.NoError(t, err)

	cfg := ReadConfig(path)
	if assert.NotNil(t, cfg) {
		// Ensure it can be marshaled back to JSON without panic
		_, err := json.Marshal(cfg)
		assert.NoError(t, err)
	}
}
