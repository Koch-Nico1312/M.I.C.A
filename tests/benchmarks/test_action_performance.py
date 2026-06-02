"""
Performance benchmarks for action modules
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestWebSearchPerformance:
    """Performance benchmarks for web_search action."""

    @pytest.fixture
    def web_search(self):
        """Create a fresh web_search instance for benchmarking."""
        from actions.web_search import web_search
        return web_search

    @patch('actions.web_search.DDGS')
    def test_search_performance(self, mock_ddgs, web_search, benchmark):
        """Benchmark web search operation."""
        mock_ddgs.return_value.__enter__.return_value.text.return_value = [
            {"title": "Result 1", "body": "Description 1", "href": "https://example.com/1"}
        ]
        
        def search():
            return web_search({"query": "test query"})
        
        result = benchmark(search)
        assert result is not None


class TestFileControllerPerformance:
    """Performance benchmarks for file_controller action."""

    @pytest.fixture
    def file_controller(self):
        """Create a fresh file_controller instance for benchmarking."""
        from actions.file_controller import file_controller
        return file_controller

    def test_file_read_performance(self, file_controller, benchmark, tmp_path):
        """Benchmark file read operations."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content" * 1000)
        
        def read_file():
            return file_controller.read(str(test_file))
        
        result = benchmark(read_file)
        assert result is not None

    def test_file_write_performance(self, file_controller, benchmark, tmp_path):
        """Benchmark file write operations."""
        test_file = tmp_path / "test.txt"
        test_content = "Test content" * 1000
        
        def write_file():
            return file_controller.write(str(test_file), test_content)
        
        result = benchmark(write_file)
        assert result is not None

    def test_file_search_performance(self, file_controller, benchmark, tmp_path):
        """Benchmark file search operations."""
        # Create test files
        for i in range(100):
            (tmp_path / f"file{i}.txt").write_text(f"Content {i}")
        
        def search_files():
            return file_controller.list(str(tmp_path))
        
        result = benchmark(search_files)
        assert result is not None


class TestBrowserControlPerformance:
    """Performance benchmarks for browser_control action."""

    @pytest.fixture
    def browser_control(self):
        """Create a fresh browser_control instance for benchmarking."""
        from actions.browser_control import browser_control
        return browser_control

    @patch('actions.browser_control.playwright')
    def test_page_load_performance(self, mock_playwright, browser_control, benchmark):
        """Benchmark page load operation."""
        mock_page = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        def load_page():
            return browser_control.navigate("https://example.com")
        
        result = benchmark(load_page)
        assert result is not None


class TestCodeHelperPerformance:
    """Performance benchmarks for code_helper action."""

    @pytest.fixture
    def code_helper(self):
        """Create a fresh code_helper instance for benchmarking."""
        from actions.code_helper import code_helper
        return code_helper

    def test_code_generation_performance(self, code_helper, benchmark):
        """Benchmark code generation."""
        def generate_code():
            return code_helper.generate(
                language="python",
                description="Create a function that adds two numbers"
            )
        
        result = benchmark(generate_code)
        assert result is not None

    def test_code_explanation_performance(self, code_helper, benchmark):
        """Benchmark code explanation."""
        code = "def add(a, b):\n    return a + b"
        
        def explain_code():
            return code_helper.explain(code)
        
        result = benchmark(explain_code)
        assert result is not None


class TestScreenProcessorPerformance:
    """Performance benchmarks for screen_processor action."""

    @pytest.fixture
    def screen_processor(self):
        """Create a fresh screen_processor instance for benchmarking."""
        from actions.screen_processor import screen_process
        return screen_processor

    @patch('actions.screen_processor.mss')
    def test_screen_capture_performance(self, mock_mss, screen_processor, benchmark):
        """Benchmark screen capture operation."""
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = MagicMock()
        mock_screenshot.size = (1920, 1080)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        
        def capture_screen():
            return screen_processor.capture()
        
        result = benchmark(capture_screen)
        assert result is not None


class TestDesktopControlPerformance:
    """Performance benchmarks for desktop_control action."""

    @pytest.fixture
    def desktop(self):
        """Create a fresh desktop instance for benchmarking."""
        from actions.desktop import desktop_control
        return desktop

    @patch('actions.desktop.pyautogui')
    def test_mouse_movement_performance(self, mock_pyautogui, desktop, benchmark):
        """Benchmark mouse movement operation."""
        mock_pyautogui.moveTo.return_value = None
        
        def move_mouse():
            return desktop.move_mouse(100, 200)
        
        result = benchmark(move_mouse)
        assert result is not None

    @patch('actions.desktop.pyautogui')
    def test_typing_performance(self, mock_pyautogui, desktop, benchmark):
        """Benchmark typing operation."""
        mock_pyautogui.typewrite.return_value = None
        
        def type_text():
            return desktop.type("Hello World")
        
        result = benchmark(type_text)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
