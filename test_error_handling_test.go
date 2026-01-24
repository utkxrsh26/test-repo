package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestReadConfig_TableDriven(t *testing.T) {
	type wantType struct {
		config map[string]interface{}
	}
	tests := []struct {
		name        string
		setupFile   bool
		fileData    []byte
		want        wantType
		shouldPanic bool
	}{
		{
			name:      "existing file with valid JSON",
			setupFile: true,
			fileData:  []byte(`{"key":"value","num":42}`),
			want: wantType{
				config: map[string]interface{}{
					"key": "value",
					"num": float64(42),
				},
			},
		},
		{
			name:      "existing file with invalid JSON",
			setupFile: true,
			fileData:  []byte(`{invalid json`),
			// json.Unmarshal will fail but error is ignored, config stays nil
			want: wantType{
				config: nil,
			},
		},
		{
			name:      "non existing file path",
			setupFile: false,
			// os.ReadFile error is ignored, data is nil, json.Unmarshal on nil -> empty map
			want: wantType{
				config: map[string]interface{}{},
			},
		},
		{
			name:        "empty file path string",
			setupFile:   false,
			shouldPanic: false,
			// os.ReadFile("") error ignored, behaves like non existing file
			want: wantType{
				config: map[string]interface{}{},
			},
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			var path string
			if tt.setupFile {
				dir := t.TempDir()
				path = filepath.Join(dir, "config.json")
				err := os.WriteFile(path, tt.fileData, 0o644)
				assert.NoError(t, err)
			} else {
				// use a path that does not exist inside temp dir
				dir := t.TempDir()
				path = filepath.Join(dir, "nonexistent.json")
			}

			got := ReadConfig(path)

			if tt.want.config == nil {
				assert.Nil(t, got)
				return
			}

			assert.NotNil(t, got)
			assert.Equal(t, tt.want.config["key"], got["key"])
			assert.Equal(t, tt.want.config["num"], got["num"])
		})
	}
}

func TestReadConfig_EmptyFileContent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "empty.json")
	err := os.WriteFile(path, []byte(""), 0o644)
	assert.NoError(t, err)

	got := ReadConfig(path)
	// json.Unmarshal on empty slice returns error, config remains nil
	assert.Nil(t, got)
}

func TestReadConfig_PartialJSON(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "partial.json")
	err := os.WriteFile(path, []byte(`{"key":"value"`), 0o644)
	assert.NoError(t, err)

	got := ReadConfig(path)
	// invalid JSON, config remains nil
	assert.Nil(t, got)
}

func TestWriteLog_TableDriven(t *testing.T) {
	tests := []struct {
		name       string
		message    string
		expectFile bool
	}{
		{
			name:       "simple message",
			message:    "hello world",
			expectFile: true,
		},
		{
			name:       "empty message",
			message:    "",
			expectFile: true,
		},
		{
			name:       "multi-line message",
			message:    "line1\nline2\nline3",
			expectFile: true,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			// change working directory to temp dir so app.log is created there
			dir := t.TempDir()
			origWD, err := os.Getwd()
			assert.NoError(t, err)
			defer func() {
				_ = os.Chdir(origWD)
			}()
			err = os.Chdir(dir)
			assert.NoError(t, err)

			WriteLog(tt.message)

			if tt.expectFile {
				data, err := os.ReadFile("app.log")
				assert.NoError(t, err)
				assert.Contains(t, string(data), tt.message)
			}
		})
	}
}

func TestWriteLog_AppendsToExistingFile(t *testing.T) {
	dir := t.TempDir()
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()
	err = os.Chdir(dir)
	assert.NoError(t, err)

	err = os.WriteFile("app.log", []byte("existing\n"), 0o644)
	assert.NoError(t, err)

	WriteLog("new entry\n")

	data, err := os.ReadFile("app.log")
	assert.NoError(t, err)
	content := string(data)
	assert.Contains(t, content, "existing\n")
	assert.Contains(t, content, "new entry\n")
}

func TestWriteLog_MultipleSequentialWrites(t *testing.T) {
	dir := t.TempDir()
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()
	err = os.Chdir(dir)
	assert.NoError(t, err)

	messages := []string{"first", "second", "third"}
	for _, msg := range messages {
		WriteLog(msg + "\n")
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
		want        string
		shouldPanic bool
	}{
		{
			name:        "non-empty string",
			input:       "data",
			want:        "data",
			shouldPanic: false,
		},
		{
			name:        "whitespace string",
			input:       "   ",
			want:        "   ",
			shouldPanic: false,
		},
		{
			name:        "empty string panics",
			input:       "",
			want:        "",
			shouldPanic: true,
		},
		{
			name:        "long string",
			input:       "this is a longer input string",
			want:        "this is a longer input string",
			shouldPanic: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			if tt.shouldPanic {
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

func TestProcessData_ReturnsSameString(t *testing.T) {
	inputs := []string{"abc", "123", "special!@#", "mixed 123 abc"}
	for _, in := range inputs {
		in := in
		t.Run("input_"+in, func(t *testing.T) {
			assert.NotPanics(t, func() {
				got := ProcessData(in)
				assert.Equal(t, in, got)
			})
		})
	}
}

func TestProcessData_PanicMessage(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			msg, ok := r.(string)
			assert.True(t, ok)
			assert.Equal(t, "empty input", msg)
		} else {
			t.Fatalf("expected panic but none occurred")
		}
	}()
	_ = ProcessData("")
}

func TestReadConfig_NilBehaviorOnInvalidJSON(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "invalid.json")
	err := os.WriteFile(path, []byte(`{"a":1`), 0o644)
	assert.NoError(t, err)

	cfg := ReadConfig(path)
	assert.Nil(t, cfg)
}

func TestReadConfig_ValidJSONDifferentTypes(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.json")
	content := map[string]interface{}{
		"str": "value",
		"num": 1,
		"arr": []interface{}{1, 2, 3},
	}
	data, err := json.Marshal(content)
	assert.NoError(t, err)
	err = os.WriteFile(path, data, 0o644)
	assert.NoError(t, err)

	cfg := ReadConfig(path)
	assert.NotNil(t, cfg)
	assert.Equal(t, "value", cfg["str"])
	assert.Equal(t, float64(1), cfg["num"])
}
