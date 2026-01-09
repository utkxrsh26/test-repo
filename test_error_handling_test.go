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
	validContent := `{"key":"value","number":123}`
	err := os.WriteFile(validPath, []byte(validContent), 0o644)
	assert.NoError(t, err)

	invalidJSONPath := filepath.Join(tmpDir, "invalid.json")
	invalidContent := `{"key": "value",}`
	err = os.WriteFile(invalidJSONPath, []byte(invalidContent), 0o644)
	assert.NoError(t, err)

	nonExistentPath := filepath.Join(tmpDir, "does_not_exist.json")

	tests := []struct {
		name       string
		path       string
		wantKeys   []string
		shouldRead bool
	}{
		{
			name:       "valid JSON file",
			path:       validPath,
			wantKeys:   []string{"key", "number"},
			shouldRead: true,
		},
		{
			name:       "invalid JSON file",
			path:       invalidJSONPath,
			wantKeys:   nil,
			shouldRead: true,
		},
		{
			name:       "non-existent file",
			path:       nonExistentPath,
			wantKeys:   nil,
			shouldRead: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			cfg := ReadConfig(tt.path)
			if tt.shouldRead {
				assert.NotNil(t, cfg)
				if cfg != nil && len(tt.wantKeys) > 0 {
					for _, k := range tt.wantKeys {
						_, ok := cfg[k]
						assert.True(t, ok)
					}
				}
			} else {
				assert.NotNil(t, cfg)
				if cfg != nil {
					assert.Equal(t, 0, len(cfg))
				}
			}
		})
	}
}

func TestReadConfig_EmptyFileAndCorruptedContent(t *testing.T) {
	tmpDir := t.TempDir()

	emptyPath := filepath.Join(tmpDir, "empty.json")
	err := os.WriteFile(emptyPath, []byte(""), 0o644)
	assert.NoError(t, err)

	partialJSONPath := filepath.Join(tmpDir, "partial.json")
	partialContent := `{"incomplete":`
	err = os.WriteFile(partialJSONPath, []byte(partialContent), 0o644)
	assert.NoError(t, err)

	tests := []struct {
		name     string
		path     string
		validate func(t *testing.T, cfg map[string]interface{})
	}{
		{
			name: "empty file returns empty map",
			path: emptyPath,
			validate: func(t *testing.T, cfg map[string]interface{}) {
				assert.NotNil(t, cfg)
				if cfg != nil {
					assert.Equal(t, 0, len(cfg))
				}
			},
		},
		{
			name: "partially valid JSON returns empty map",
			path: partialJSONPath,
			validate: func(t *testing.T, cfg map[string]interface{}) {
				assert.NotNil(t, cfg)
				if cfg != nil {
					assert.Equal(t, 0, len(cfg))
				}
			},
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			cfg := ReadConfig(tt.path)
			tt.validate(t, cfg)
		})
	}
}

func TestReadConfig_ModifiedContent(t *testing.T) {
	tmpDir := t.TempDir()

	path := filepath.Join(tmpDir, "config.json")
	initial := map[string]interface{}{
		"enabled": true,
		"count":   float64(5),
	}
	initialBytes, err := json.Marshal(initial)
	assert.NoError(t, err)

	err = os.WriteFile(path, initialBytes, 0o644)
	assert.NoError(t, err)

	cfg1 := ReadConfig(path)
	assert.NotNil(t, cfg1)
	if cfg1 != nil {
		assert.Equal(t, initial["enabled"], cfg1["enabled"])
		assert.Equal(t, initial["count"], cfg1["count"])
	}

	updated := map[string]interface{}{
		"enabled": false,
		"count":   float64(10),
	}
	updatedBytes, err := json.Marshal(updated)
	assert.NoError(t, err)

	err = os.WriteFile(path, updatedBytes, 0o644)
	assert.NoError(t, err)

	cfg2 := ReadConfig(path)
	assert.NotNil(t, cfg2)
	if cfg2 != nil {
		assert.Equal(t, updated["enabled"], cfg2["enabled"])
		assert.Equal(t, updated["count"], cfg2["count"])
	}
}

func TestWriteLog_TableDriven(t *testing.T) {
	tmpDir := t.TempDir()
	logPath := filepath.Join(tmpDir, "app.log")

	origWd, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWd)
	}()

	tests := []struct {
		name    string
		message string
	}{
		{
			name:    "simple message",
			message: "hello world",
		},
		{
			name:    "empty message",
			message: "",
		},
		{
			name:    "multi-line message",
			message: "line1\nline2\nline3",
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			WriteLog(tt.message)

			data, err := os.ReadFile(logPath)
			assert.NoError(t, err)
			content := string(data)
			assert.Contains(t, content, tt.message)
		})
	}
}

func TestWriteLog_AppendsContent(t *testing.T) {
	tmpDir := t.TempDir()
	logPath := filepath.Join(tmpDir, "app.log")

	origWd, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWd)
	}()

	initial := "first line\n"
	err = os.WriteFile(logPath, []byte(initial), 0o644)
	assert.NoError(t, err)

	messages := []string{"second line", "third line", "fourth line"}
	for _, msg := range messages {
		WriteLog(msg)
	}

	data, err := os.ReadFile(logPath)
	assert.NoError(t, err)
	content := string(data)

	assert.Contains(t, content, initial)
	for _, msg := range messages {
		assert.Contains(t, content, msg)
	}
}

func TestWriteLog_LogFileCreatedIfMissing(t *testing.T) {
	tmpDir := t.TempDir()
	logPath := filepath.Join(tmpDir, "app.log")

	origWd, err := os.Getwd()
	assert.NoError(t, err)
	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWd)
	}()

	_, err = os.Stat(logPath)
	assert.True(t, os.IsNotExist(err))

	WriteLog("created by WriteLog")

	info, err := os.Stat(logPath)
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
			name:      "non-empty string",
			input:     "hello",
			want:      "hello",
			wantPanic: false,
		},
		{
			name:      "whitespace string",
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
			name:      "long string",
			input:     "this is a longer input string for testing",
			want:      "this is a longer input string for testing",
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

func TestProcessData_RepeatedCalls(t *testing.T) {
	inputs := []string{"a", "b", "c", "d", "e"}
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
	assert.PanicsWithValue(t, "empty input", func() {
		_ = ProcessData("")
	})
}
