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
		setupFile   func(t *testing.T, dir string) string
		want        wantType
		shouldPanic bool
	}{
		{
			name: "valid JSON file returns parsed map",
			setupFile: func(t *testing.T, dir string) string {
				t.Helper()
				content := `{"key":"value","num":42}`
				path := filepath.Join(dir, "config_valid.json")
				err := os.WriteFile(path, []byte(content), 0o644)
				assert.NoError(t, err)
				return path
			},
			want: wantType{
				config: map[string]interface{}{
					"key": "value",
					"num": float64(42),
				},
			},
			shouldPanic: false,
		},
		{
			name: "nonexistent file returns nil map due to ignored error",
			setupFile: func(t *testing.T, dir string) string {
				t.Helper()
				return filepath.Join(dir, "does_not_exist.json")
			},
			want: wantType{
				config: nil,
			},
			shouldPanic: false,
		},
		{
			name: "invalid JSON returns nil map due to ignored unmarshal error",
			setupFile: func(t *testing.T, dir string) string {
				t.Helper()
				content := `{"key": invalid json}`
				path := filepath.Join(dir, "config_invalid.json")
				err := os.WriteFile(path, []byte(content), 0o644)
				assert.NoError(t, err)
				return path
			},
			want: wantType{
				config: nil,
			},
			shouldPanic: false,
		},
	}

	tmpDir := t.TempDir()

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			path := tt.setupFile(t, tmpDir)
			got := ReadConfig(path)

			if tt.want.config == nil {
				assert.Nil(t, got)
				return
			}

			assert.NotNil(t, got)
			assert.Equal(t, tt.want.config["key"], got["key"])

			wantNum, okWant := tt.want.config["num"].(float64)
			gotNum, okGot := got["num"].(float64)
			assert.True(t, okWant)
			assert.True(t, okGot)
			assert.Equal(t, wantNum, gotNum)
		})
	}
}

func TestReadConfig_EmptyFileBehavior(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "empty.json")
	err := os.WriteFile(path, []byte(""), 0o644)
	assert.NoError(t, err)

	got := ReadConfig(path)
	assert.Nil(t, got)
}

func TestReadConfig_PartialJSON(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "partial.json")
	type custom struct {
		A string `json:"a"`
	}
	contentStruct := custom{A: "test"}
	contentBytes, err := json.Marshal(contentStruct)
	assert.NoError(t, err)
	err = os.WriteFile(path, contentBytes, 0o644)
	assert.NoError(t, err)

	got := ReadConfig(path)
	assert.NotNil(t, got)
	assert.Equal(t, "test", got["a"])
}

func TestWriteLog_TableDriven(t *testing.T) {
	tests := []struct {
		name      string
		setup     func(t *testing.T) func()
		message   string
		expectLog bool
	}{
		{
			name: "write simple message appends to log file",
			setup: func(t *testing.T) func() {
				t.Helper()
				_ = os.Remove("app.log")
				return func() {
					_ = os.Remove("app.log")
				}
			},
			message:   "hello world",
			expectLog: true,
		},
		{
			name: "multiple writes append sequentially",
			setup: func(t *testing.T) func() {
				t.Helper()
				_ = os.Remove("app.log")
				return func() {
					_ = os.Remove("app.log")
				}
			},
			message:   "first\nsecond\n",
			expectLog: true,
		},
		{
			name: "write empty message still touches file",
			setup: func(t *testing.T) func() {
				t.Helper()
				_ = os.Remove("app.log")
				return func() {
					_ = os.Remove("app.log")
				}
			},
			message:   "",
			expectLog: true,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			cleanup := tt.setup(t)
			defer cleanup()

			WriteLog(tt.message)

			info, err := os.Stat("app.log")
			if tt.expectLog {
				assert.NoError(t, err)
				assert.False(t, info.IsDir())
				data, readErr := os.ReadFile("app.log")
				assert.NoError(t, readErr)
				assert.Contains(t, string(data), tt.message)
			} else {
				assert.Error(t, err)
			}
		})
	}
}

func TestWriteLog_AppendsToExistingFile(t *testing.T) {
	_ = os.Remove("app.log")
	initialContent := "existing\n"
	err := os.WriteFile("app.log", []byte(initialContent), 0o644)
	assert.NoError(t, err)

	WriteLog("new line\n")

	data, readErr := os.ReadFile("app.log")
	assert.NoError(t, readErr)
	content := string(data)
	assert.Contains(t, content, initialContent)
	assert.Contains(t, content, "new line\n")
}

func TestWriteLog_FilePermissions(t *testing.T) {
	_ = os.Remove("app.log")
	WriteLog("check perms")

	info, err := os.Stat("app.log")
	assert.NoError(t, err)
	assert.False(t, info.IsDir())
}

func TestProcessData_TableDriven(t *testing.T) {
	tests := []struct {
		name        string
		input       string
		shouldPanic bool
	}{
		{
			name:        "non-empty input returns same string",
			input:       "data",
			shouldPanic: false,
		},
		{
			name:        "whitespace input does not panic",
			input:       " ",
			shouldPanic: false,
		},
		{
			name:        "empty input panics",
			input:       "",
			shouldPanic: true,
		},
		{
			name:        "long input returns same string",
			input:       "this is a long input string for testing",
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
				assert.Equal(t, tt.input, got)
			})
		})
	}
}

func TestProcessData_EmptyAndNonEmptySeparate(t *testing.T) {
	assert.Panics(t, func() {
		_ = ProcessData("")
	})

	result := ProcessData("ok")
	assert.Equal(t, "ok", result)
}

func TestProcessData_RepeatedCalls(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	for _, in := range inputs {
		out := ProcessData(in)
		assert.Equal(t, in, out)
	}
}
