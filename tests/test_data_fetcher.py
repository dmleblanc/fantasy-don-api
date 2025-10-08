import json
import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime, timezone
import sys
import os

# Add lambda functions to path and import using importlib to avoid conflicts
import importlib.util

data_fetcher_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../lambda_functions/data_fetcher/index.py')
)

spec = importlib.util.spec_from_file_location("data_fetcher_index", data_fetcher_path)
data_fetcher_module = importlib.util.module_from_spec(spec)
sys.modules['data_fetcher_index'] = data_fetcher_module  # Register in sys.modules for @patch
spec.loader.exec_module(data_fetcher_module)

get_nfl_stats = data_fetcher_module.get_nfl_stats
save_to_s3 = data_fetcher_module.save_to_s3
handler = data_fetcher_module.handler


class TestGetNFLStats:
    """Test suite for get_nfl_stats function."""

    def test_returns_dict(self):
        """Test that get_nfl_stats returns a dictionary."""
        result = get_nfl_stats()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """Test that result has all required top-level keys."""
        result = get_nfl_stats()
        required_keys = ['timestamp', 'source', 'data', 'metadata']

        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    def test_timestamp_format(self):
        """Test that timestamp is in ISO format."""
        result = get_nfl_stats()

        # Should be able to parse as ISO format
        timestamp = result['timestamp']
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert isinstance(parsed, datetime)

    def test_data_structure(self):
        """Test that data section has expected structure."""
        result = get_nfl_stats()
        data = result['data']

        assert 'players' in data
        assert 'teams' in data
        assert 'games' in data
        assert isinstance(data['players'], list)
        assert isinstance(data['teams'], list)
        assert isinstance(data['games'], list)

    def test_metadata_structure(self):
        """Test that metadata has expected fields."""
        result = get_nfl_stats()
        metadata = result['metadata']

        assert 'fetch_date' in metadata
        assert 'season' in metadata

        # Verify date format YYYY-MM-DD
        fetch_date = metadata['fetch_date']
        datetime.strptime(fetch_date, '%Y-%m-%d')

        # Verify season is an integer
        assert isinstance(metadata['season'], int)

    def test_source_field(self):
        """Test that source is set correctly."""
        result = get_nfl_stats()
        assert result['source'] == 'nfl_stats_py'


class TestSaveToS3:
    """Test suite for save_to_s3 function."""

    @patch('data_fetcher_index.s3_client')
    def test_saves_with_date_structure(self, mock_s3):
        """Test that S3 key follows date-based structure."""
        test_data = {'test': 'data'}
        bucket_name = 'test-bucket'
        prefix = 'stats/'

        result = save_to_s3(test_data, bucket_name, prefix)

        # Should have called put_object twice (dated + latest)
        assert mock_s3.put_object.call_count == 2

        # Verify key structure: stats/YYYY/MM/DD/HH-MM-SS.json
        first_call = mock_s3.put_object.call_args_list[0]
        s3_key = first_call[1]['Key']

        assert s3_key.startswith(prefix)
        assert s3_key.endswith('.json')
        assert result == s3_key

    @patch('data_fetcher_index.s3_client')
    def test_saves_latest_file(self, mock_s3):
        """Test that a 'latest.json' file is also saved."""
        test_data = {'test': 'data'}
        bucket_name = 'test-bucket'
        prefix = 'stats/'

        save_to_s3(test_data, bucket_name, prefix)

        # Second call should be for latest.json
        second_call = mock_s3.put_object.call_args_list[1]
        latest_key = second_call[1]['Key']

        assert latest_key == f'{prefix}latest.json'

    @patch('data_fetcher_index.s3_client')
    def test_data_is_json_string(self, mock_s3):
        """Test that data is saved as JSON string."""
        test_data = {'test': 'data', 'number': 42}
        bucket_name = 'test-bucket'
        prefix = 'stats/'

        save_to_s3(test_data, bucket_name, prefix)

        # Get the Body parameter from first call
        first_call = mock_s3.put_object.call_args_list[0]
        body = first_call[1]['Body']

        # Should be able to parse back to original data
        parsed = json.loads(body)
        assert parsed == test_data

    @patch('data_fetcher_index.s3_client')
    def test_sets_content_type(self, mock_s3):
        """Test that ContentType is set to application/json."""
        test_data = {'test': 'data'}

        save_to_s3(test_data, 'bucket', 'prefix/')

        # Check both calls
        for call in mock_s3.put_object.call_args_list:
            assert call[1]['ContentType'] == 'application/json'

    @patch('data_fetcher_index.s3_client')
    def test_sets_metadata(self, mock_s3):
        """Test that S3 metadata is set."""
        test_data = {'test': 'data'}

        save_to_s3(test_data, 'bucket', 'prefix/')

        # Check metadata
        first_call = mock_s3.put_object.call_args_list[0]
        metadata = first_call[1]['Metadata']

        assert 'fetch_timestamp' in metadata
        assert 'data_type' in metadata
        assert metadata['data_type'] == 'nfl_stats'

    @patch('data_fetcher_index.s3_client')
    def test_handles_s3_error(self, mock_s3):
        """Test that S3 errors are properly raised."""
        from botocore.exceptions import ClientError

        mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'PutObject'
        )

        with pytest.raises(ClientError):
            save_to_s3({'test': 'data'}, 'bucket', 'prefix/')


class TestHandler:
    """Test suite for Lambda handler function."""

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('data_fetcher_index.save_to_s3')
    @patch('data_fetcher_index.get_nfl_stats')
    def test_successful_execution(self, mock_get_stats, mock_save):
        """Test successful handler execution."""
        # Setup mocks
        mock_stats = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'players': [{'id': 1}, {'id': 2}],
                'teams': [{'id': 1}],
                'games': []
            }
        }
        mock_get_stats.return_value = mock_stats
        mock_save.return_value = 'stats/2025/10/04/12-00-00.json'

        # Execute
        result = handler({}, None)

        # Verify
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['message'] == 'NFL stats fetched and stored successfully'
        assert body['s3_key'] == 'stats/2025/10/04/12-00-00.json'
        assert body['bucket'] == 'test-bucket'
        assert body['record_count']['players'] == 2
        assert body['record_count']['teams'] == 1

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket'})
    @patch('data_fetcher_index.save_to_s3')
    @patch('data_fetcher_index.get_nfl_stats')
    def test_calls_functions_in_order(self, mock_get_stats, mock_save):
        """Test that get_nfl_stats is called before save_to_s3."""
        mock_stats = {'data': {'players': [], 'teams': [], 'games': []}}
        mock_get_stats.return_value = mock_stats
        mock_save.return_value = 'test-key.json'

        handler({}, None)

        # Verify both were called
        mock_get_stats.assert_called_once()
        mock_save.assert_called_once_with(mock_stats, 'test-bucket', 'stats/')

    @patch.dict(os.environ, {})
    def test_missing_bucket_env_var(self):
        """Test error when BUCKET_NAME environment variable is missing."""
        with pytest.raises(ValueError, match='BUCKET_NAME environment variable not set'):
            handler({}, None)

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket'})
    @patch('data_fetcher_index.get_nfl_stats')
    def test_handles_fetch_error(self, mock_get_stats):
        """Test error handling when stats fetching fails."""
        mock_get_stats.side_effect = Exception('API Error')

        result = handler({}, None)

        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert body['message'] == 'Failed to fetch NFL stats'
        assert 'API Error' in body['error']

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket'})
    @patch('data_fetcher_index.save_to_s3')
    @patch('data_fetcher_index.get_nfl_stats')
    def test_handles_save_error(self, mock_get_stats, mock_save):
        """Test error handling when S3 save fails."""
        from botocore.exceptions import ClientError

        mock_get_stats.return_value = {'data': {'players': [], 'teams': [], 'games': []}}
        mock_save.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'PutObject'
        )

        result = handler({}, None)

        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert 'Failed to fetch NFL stats' in body['message']

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'custom-prefix/'})
    @patch('data_fetcher_index.save_to_s3')
    @patch('data_fetcher_index.get_nfl_stats')
    def test_uses_custom_prefix(self, mock_get_stats, mock_save):
        """Test that custom DATA_PREFIX is used."""
        mock_get_stats.return_value = {'data': {'players': [], 'teams': [], 'games': []}}
        mock_save.return_value = 'test-key.json'

        handler({}, None)

        # Verify save_to_s3 called with custom prefix
        mock_save.assert_called_once_with(ANY, 'test-bucket', 'custom-prefix/')

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket'})
    @patch('data_fetcher_index.save_to_s3')
    @patch('data_fetcher_index.get_nfl_stats')
    def test_response_includes_timestamp(self, mock_get_stats, mock_save):
        """Test that response includes timestamp."""
        mock_get_stats.return_value = {'data': {'players': [], 'teams': [], 'games': []}}
        mock_save.return_value = 'test-key.json'

        result = handler({}, None)

        body = json.loads(result['body'])
        assert 'timestamp' in body

        # Should be valid ISO format
        timestamp = datetime.fromisoformat(body['timestamp'].replace('Z', '+00:00'))
        assert isinstance(timestamp, datetime)
