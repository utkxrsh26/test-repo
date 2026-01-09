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

	validConfigPath := filepath.Join(tmpDir, "valid.json")
	validContent := `{"key":"value","num":42}`
	err := os.WriteFile(validConfigPath, []byte(validContent), 0o644)
	assert.NoError(t, err)

	invalidJSONPath := filepath.Join(tmpDir, "invalid.json")
	invalidContent := `{"key":`
	err = os.WriteFile(invalidJSONPath, []byte(invalidContent), 0o644)
	assert.NoError(t, err)

	emptyFilePath := filepath.Join(tmpDir, "empty.json")
	err = os.WriteFile(emptyFilePath, []byte(""), 0o644)
	assert.NoError(t, err)

	tests := []struct {
		name        string
		path        string
		setup       func()
		expectEmpty bool
	}{
		{
			name: "nonexistent file returns nil map (panic avoided)",
			path: filepath.Join(tmpDir, "does_not_exist.json"),
		},
		{
			name:        "valid JSON file returns populated map",
			path:        validConfigPath,
			expectEmpty: false,
		},
		{
			name:        "invalid JSON returns nil map",
			path:        invalidJSONPath,
			expectEmpty: true,
		},
		{
			name:        "empty file returns nil map",
			path:        emptyFilePath,
			expectEmpty: true,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			cfg := ReadConfig(tt.path)

			if tt.path == validConfigPath {
				assert.NotNil(t, cfg)
				if cfg != nil {
					assert.Equal(t, "value", cfg["key"])
					// json.Unmarshal decodes numbers as float64 by default
					num, ok := cfg["num"].(float64)
					assert.True(t, ok)
					if ok {
						assert.Equal(t, float64(42), num)
					}
				}
				return
			}

			if tt.expectEmpty {
				if cfg != nil {
					// For invalid/empty JSON, config will remain nil
					// but if implementation changes, ensure it's empty
					b, err := json.Marshal(cfg)
					assert.NoError(t, err)
					assert.True(t, string(b) == "null" || string(b) == "{}", "expected nil or empty map")
				}
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
	if cfg1 != nil && cfg2 != nil {
		assert.NotEqual(t, cfg1, cfg2)
		assert.Contains(t, cfg1, "a")
		assert.NotContains(t, cfg1, "b")
		assert.Contains(t, cfg2, "b")
		assert.NotContains(t, cfg2, "a")
	}
}

func TestWriteLog_TableDriven(t *testing.T) {
	tmpDir := t.TempDir()
	logPath := filepath.Join(tmpDir, "app.log")

	// Change working directory so WriteLog writes into tmpDir
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
		repeat      int
		expectLines int
	}{
		{
			name:        "single write appends message",
			message:     "hello",
			repeat:      1,
			expectLines: 1,
		},
		{
			name:        "multiple writes append multiple messages",
			message:     "world",
			repeat:      3,
			expectLines: 4, // 1 from previous test case + 3 new
		},
		{
			name:        "empty message still writes",
			message:     "",
			repeat:      2,
			expectLines: 6, // 4 previous + 2 empty
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			for i := 0; i < tt.repeat; i++ {
				WriteLog(tt.message)
			}

			data, err := os.ReadFile(logPath)
			assert.NoError(t, err)

			// Count lines by counting '\n' and last line if no trailing newline
			content := string(data)
			lines := 0
			for i := 0; i < len(content); i++ {
				if content[i] == '\n' {
					lines++
				}
			}
			if len(content) > 0 && content[len(content)-1] != '\n' {
				lines++
			}

			assert.Equal(t, tt.expectLines, lines)
		})
	}
}

func TestWriteLog_FileCreatedIfNotExists(t *testing.T) {
	tmpDir := t.TempDir()

	origWD, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	_, err = os.Stat("app.log")
	assert.True(t, os.IsNotExist(err))

	WriteLog("first line")

	info, err := os.Stat("app.log")
	assert.NoError(t, err)
	assert.False(t, info.IsDir())
	assert.Greater(t, info.Size(), int64(0))
}

func TestProcessData_TableDriven(t *testing.T) {
	tests := []struct {
		name      string
		input     string
		want      string
		wantPanic bool
	}{
		{
			name:      "non-empty string returns same string",
			input:     "data",
			want:      "data",
			wantPanic: false,
		},
		{
			name:      "whitespace string does not panic",
			input:     "   ",
			want:      "   ",
			wantPanic: false,
		},
		{
			name:      "empty string panics",
			input:     "",
			want:      "",
			wantPanic: true,
		},
		{
			name:      "long string returns same long string",
			input:     "abcdefghijklmnopqrstuvwxyz",
			want:      "abcdefghijklmnopqrstuvwxyz",
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

func TestProcessData_MultipleSequentialCalls(t *testing.T) {
	inputs := []string{"one", "two", "three"}
	for _, in := range inputs {
		out := ProcessData(in)
		assert.Equal(t, in, out)
	}
}

func TestProcessData_PanicMessage(t *testing.T) {
	assert.PanicsWithValue(t, "empty input", func() {
		_ = ProcessData("")
	})
}
