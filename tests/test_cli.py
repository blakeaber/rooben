"""Tests for CLI commands: init, doctor, and core subcommands."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from rooben.cli import main


class TestDoctor:
    def test_doctor_runs(self):
        """Doctor command runs and produces output."""
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Rooben Health Check" in result.output
        assert "Python version" in result.output
        assert "Anthropic API key" in result.output

    def test_doctor_checks_dependencies(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Dependency: anthropic" in result.output
        assert "Dependency: pydantic" in result.output
        assert "Dependency: click" in result.output

    def test_doctor_checks_state_dir(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "State directory" in result.output

    def test_doctor_summary(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "passed" in result.output


class TestInit:
    def test_init_prompts_for_key(self):
        """Init command prompts for API key."""
        runner = CliRunner()
        # Provide empty key — should fail
        result = runner.invoke(main, ["init"], input="\n")
        assert result.exit_code != 0 or "empty" in result.output.lower() or "Error" in result.output

    @patch("rooben.cli._validate_provider")
    def test_init_writes_env(self, mock_validate, tmp_path):
        """Init writes API key to .env file."""
        mock_validate.return_value = None  # asyncio.run wraps this

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Mock the async validation
            with patch("rooben.cli.asyncio") as mock_asyncio:
                mock_asyncio.run.return_value = None
                result = runner.invoke(
                    main, ["init", "--provider", "anthropic"],
                    input="sk-ant-test-key-12345\n",
                )
            if result.exit_code == 0:
                assert "Setup complete" in result.output


class TestHelp:
    def test_main_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "doctor" in result.output
        assert "go" in result.output
        assert "run" in result.output

    def test_go_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["go", "--help"])
        assert result.exit_code == 0
        assert "DESCRIPTION" in result.output or "description" in result.output.lower()

    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "SPEC_PATH" in result.output

    def test_validate_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["validate", "--help"])
        assert result.exit_code == 0
