import json
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
from botocore.exceptions import ClientError
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

save_to_s3 = data_fetcher_module.save_to_s3


class TestS3WriteOperations:
    """Test suite for S3 write operations with edge cases."""

    @patch('data_fetcher_index.s3_client')
    def test_writes_to_correct_bucket(self, mock_s3):
        """Test that data is written to the specified bucket."""
        test_data = {'test': 'data'}
        bucket_name = 'my-nfl-stats-bucket'

        save_to_s3(test_data, bucket_name, 'stats/')

        # Both calls should use the correct bucket
        for call_args in mock_s3.put_object.call_args_list:
            assert call_args[1]['Bucket'] == bucket_name

    @patch('data_fetcher_index.s3_client')
    def test_creates_timestamped_key(self, mock_s3):
        """Test that timestamped S3 key is created with proper format."""
        test_data = {'test': 'data'}

        with patch('index.datetime') as mock_datetime:
            # Mock a specific datetime
            mock_now = datetime(2025, 10, 4, 15, 30, 45, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            save_to_s3(test_data, 'bucket', 'stats/')

            # First call should be timestamped file
            first_call = mock_s3.put_object.call_args_list[0]
            key = first_call[1]['Key']

            assert key == 'stats/2025/10/04/15-30-45.json'

    @patch('data_fetcher_index.s3_client')
    def test_overwrites_latest_file(self, mock_s3):
        """Test that latest.json is overwritten on each save."""
        test_data = {'test': 'data'}

        # Save multiple times
        save_to_s3(test_data, 'bucket', 'stats/')
        save_to_s3({'new': 'data'}, 'bucket', 'stats/')

        # Should have 4 calls total (2 timestamped + 2 latest)
        assert mock_s3.put_object.call_count == 4

        # Check that latest.json was written both times
        latest_calls = [c for c in mock_s3.put_object.call_args_list
                       if c[1]['Key'] == 'stats/latest.json']
        assert len(latest_calls) == 2

    @patch('data_fetcher_index.s3_client')
    @patch('data_fetcher_index.datetime')
    def test_handles_concurrent_writes(self, mock_datetime, mock_s3):
        """Test that concurrent writes with different timestamps don't conflict."""
        from datetime import datetime, timezone

        # Simulate multiple writes at different times
        keys_written = []
        timestamps = [
            datetime(2025, 10, 4, 15, 30, 45, tzinfo=timezone.utc),
            datetime(2025, 10, 4, 15, 30, 46, tzinfo=timezone.utc),
            datetime(2025, 10, 4, 15, 30, 47, tzinfo=timezone.utc),
        ]

        call_count = [0]

        def capture_key(*args, **kwargs):
            keys_written.append(kwargs['Key'])

        def mock_now(*args, **kwargs):
            idx = call_count[0] // 2  # Each save_to_s3 calls datetime.now twice
            call_count[0] += 1
            return timestamps[min(idx, len(timestamps) - 1)]

        mock_s3.put_object.side_effect = capture_key
        mock_datetime.now.side_effect = mock_now

        # Write multiple times
        for i in range(3):
            save_to_s3({'iteration': i}, 'bucket', 'stats/')

        # Filter out latest.json entries
        timestamped_keys = [k for k in keys_written if 'latest.json' not in k]

        # All timestamped keys should be unique (different seconds)
        assert len(set(timestamped_keys)) == len(timestamped_keys)
        assert len(timestamped_keys) == 3

    @patch('data_fetcher_index.s3_client')
    def test_handles_access_denied_error(self, mock_s3):
        """Test handling of AccessDenied error."""
        mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'PutObject'
        )

        with pytest.raises(ClientError) as exc_info:
            save_to_s3({'test': 'data'}, 'bucket', 'stats/')

        assert exc_info.value.response['Error']['Code'] == 'AccessDenied'

    @patch('data_fetcher_index.s3_client')
    def test_handles_bucket_not_found_error(self, mock_s3):
        """Test handling of NoSuchBucket error."""
        mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket', 'Message': 'The specified bucket does not exist'}},
            'PutObject'
        )

        with pytest.raises(ClientError) as exc_info:
            save_to_s3({'test': 'data'}, 'nonexistent-bucket', 'stats/')

        assert exc_info.value.response['Error']['Code'] == 'NoSuchBucket'

    @patch('data_fetcher_index.s3_client')
    def test_handles_network_timeout(self, mock_s3):
        """Test handling of network timeout errors."""
        from botocore.exceptions import EndpointConnectionError

        mock_s3.put_object.side_effect = EndpointConnectionError(
            endpoint_url='https://s3.amazonaws.com'
        )

        with pytest.raises(EndpointConnectionError):
            save_to_s3({'test': 'data'}, 'bucket', 'stats/')

    @patch('data_fetcher_index.s3_client')
    def test_handles_invalid_json_gracefully(self, mock_s3):
        """Test that invalid JSON data is handled (should not fail since json.dumps handles it)."""
        # Python json.dumps can handle most data types
        test_data = {
            'string': 'value',
            'number': 42,
            'float': 3.14,
            'bool': True,
            'null': None,
            'list': [1, 2, 3],
            'nested': {'key': 'value'}
        }

        save_to_s3(test_data, 'bucket', 'stats/')

        # Should successfully call put_object
        assert mock_s3.put_object.call_count == 2

    @patch('data_fetcher_index.s3_client')
    def test_large_data_payload(self, mock_s3):
        """Test handling of large data payloads."""
        # Create a large dataset
        large_data = {
            'players': [
                {'id': i, 'name': f'Player {i}', 'stats': {'points': i * 10}}
                for i in range(1000)
            ]
        }

        save_to_s3(large_data, 'bucket', 'stats/')

        # Verify data was serialized correctly
        first_call = mock_s3.put_object.call_args_list[0]
        body = first_call[1]['Body']

        # Should be able to deserialize
        parsed = json.loads(body)
        assert len(parsed['players']) == 1000

    @patch('data_fetcher_index.s3_client')
    def test_empty_data_payload(self, mock_s3):
        """Test handling of empty data."""
        empty_data = {}

        save_to_s3(empty_data, 'bucket', 'stats/')

        # Should still write to S3
        assert mock_s3.put_object.call_count == 2

        first_call = mock_s3.put_object.call_args_list[0]
        body = first_call[1]['Body']
        parsed = json.loads(body)
        assert parsed == {}

    @patch('data_fetcher_index.s3_client')
    def test_special_characters_in_data(self, mock_s3):
        """Test handling of special characters in data."""
        special_data = {
            'team': "L'équipe français",
            'player': "O'Brien",
            'unicode': '🏈⚡️',
            'escaped': 'Line 1\nLine 2\tTabbed',
        }

        save_to_s3(special_data, 'bucket', 'stats/')

        # Verify data integrity
        first_call = mock_s3.put_object.call_args_list[0]
        body = first_call[1]['Body']
        parsed = json.loads(body)

        assert parsed['team'] == "L'équipe français"
        assert parsed['unicode'] == '🏈⚡️'

    @patch('data_fetcher_index.s3_client')
    def test_prefix_handling(self, mock_s3):
        """Test different prefix scenarios."""
        test_data = {'test': 'data'}

        # Test with trailing slash
        save_to_s3(test_data, 'bucket', 'stats/')
        key_with_slash = mock_s3.put_object.call_args_list[0][1]['Key']
        assert key_with_slash.startswith('stats/')

        mock_s3.reset_mock()

        # Test without trailing slash
        save_to_s3(test_data, 'bucket', 'stats')
        key_without_slash = mock_s3.put_object.call_args_list[0][1]['Key']
        assert key_without_slash.startswith('stats')

        mock_s3.reset_mock()

        # Test empty prefix
        save_to_s3(test_data, 'bucket', '')
        key_no_prefix = mock_s3.put_object.call_args_list[0][1]['Key']
        assert not key_no_prefix.startswith('/')

    @patch('data_fetcher_index.s3_client')
    def test_metadata_timestamps_match_key(self, mock_s3):
        """Test that metadata timestamps are consistent."""
        test_data = {'test': 'data'}

        with patch('index.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 4, 15, 30, 45, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            save_to_s3(test_data, 'bucket', 'stats/')

            # Check metadata timestamp
            first_call = mock_s3.put_object.call_args_list[0]
            metadata = first_call[1]['Metadata']

            assert 'fetch_timestamp' in metadata
            assert metadata['fetch_timestamp'] == mock_now.isoformat()

    @patch('data_fetcher_index.s3_client')
    def test_partial_write_failure(self, mock_s3):
        """Test handling when first write succeeds but second fails."""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second call (latest.json)
                raise ClientError(
                    {'Error': {'Code': 'InternalError', 'Message': 'Internal Error'}},
                    'PutObject'
                )

        mock_s3.put_object.side_effect = side_effect

        # Should raise error on second write
        with pytest.raises(ClientError):
            save_to_s3({'test': 'data'}, 'bucket', 'stats/')

        # First call should have succeeded
        assert call_count == 2

    @patch('data_fetcher_index.s3_client')
    def test_returns_timestamped_key(self, mock_s3):
        """Test that function returns the timestamped S3 key, not latest.json."""
        test_data = {'test': 'data'}

        result = save_to_s3(test_data, 'bucket', 'stats/')

        # Should return timestamped key
        assert result.endswith('.json')
        assert 'latest' not in result
        assert result.startswith('stats/')

    @patch('data_fetcher_index.s3_client')
    def test_content_type_is_application_json(self, mock_s3):
        """Test that ContentType is always application/json."""
        test_data = {'test': 'data'}

        save_to_s3(test_data, 'bucket', 'stats/')

        # Check all calls
        for call_args in mock_s3.put_object.call_args_list:
            assert call_args[1]['ContentType'] == 'application/json'

    @patch('data_fetcher_index.s3_client')
    def test_data_type_metadata_is_set(self, mock_s3):
        """Test that data_type metadata is set correctly."""
        test_data = {'test': 'data'}

        save_to_s3(test_data, 'bucket', 'stats/')

        # Check all calls
        for call_args in mock_s3.put_object.call_args_list:
            metadata = call_args[1]['Metadata']
            assert metadata['data_type'] == 'nfl_stats'

    @patch('data_fetcher_index.s3_client')
    @patch('data_fetcher_index.print')
    def test_logs_success_messages(self, mock_print, mock_s3):
        """Test that success messages are logged."""
        test_data = {'test': 'data'}

        save_to_s3(test_data, 'test-bucket', 'stats/')

        # Should print success messages
        print_calls = [str(call) for call in mock_print.call_args_list]

        # Should mention successful save
        assert any('Successfully saved' in str(call) for call in print_calls)

    @patch('data_fetcher_index.s3_client')
    def test_json_formatting_is_pretty(self, mock_s3):
        """Test that JSON is formatted with indentation."""
        test_data = {'key1': 'value1', 'key2': {'nested': 'value2'}}

        save_to_s3(test_data, 'bucket', 'stats/')

        first_call = mock_s3.put_object.call_args_list[0]
        body = first_call[1]['Body']

        # Should have indentation (pretty printed)
        assert '\n' in body
        assert '  ' in body  # 2-space indentation

    @patch('data_fetcher_index.s3_client')
    def test_both_files_have_identical_content(self, mock_s3):
        """Test that timestamped and latest.json have identical content."""
        test_data = {'test': 'data', 'number': 42}

        save_to_s3(test_data, 'bucket', 'stats/')

        # Get both bodies
        first_body = mock_s3.put_object.call_args_list[0][1]['Body']
        second_body = mock_s3.put_object.call_args_list[1][1]['Body']

        # Parse and compare
        first_data = json.loads(first_body)
        second_data = json.loads(second_body)

        assert first_data == second_data == test_data


class TestS3EdgeCases:
    """Additional edge case tests for S3 operations."""

    @patch('data_fetcher_index.s3_client')
    def test_handles_throttling_error(self, mock_s3):
        """Test handling of S3 throttling (SlowDown) error."""
        mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': 'SlowDown', 'Message': 'Please reduce your request rate'}},
            'PutObject'
        )

        with pytest.raises(ClientError) as exc_info:
            save_to_s3({'test': 'data'}, 'bucket', 'stats/')

        assert exc_info.value.response['Error']['Code'] == 'SlowDown'

    @patch('data_fetcher_index.s3_client')
    def test_handles_invalid_bucket_name(self, mock_s3):
        """Test handling of invalid bucket name."""
        mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': 'InvalidBucketName', 'Message': 'The specified bucket is not valid'}},
            'PutObject'
        )

        with pytest.raises(ClientError):
            save_to_s3({'test': 'data'}, 'invalid..bucket..name', 'stats/')

    @patch('data_fetcher_index.s3_client')
    def test_same_second_writes_overwrite(self, mock_s3):
        """Test that writes in the same second create the same key (overwrite behavior)."""
        test_data = {'test': 'data'}

        with patch('index.datetime') as mock_datetime:
            # Lock time to same second
            mock_now = datetime(2025, 10, 4, 15, 30, 45, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            # Write twice
            key1 = save_to_s3(test_data, 'bucket', 'stats/')
            key2 = save_to_s3({'different': 'data'}, 'bucket', 'stats/')

            # Keys should be identical (would overwrite in S3)
            assert key1 == key2
            assert key1 == 'stats/2025/10/04/15-30-45.json'

    @patch('data_fetcher_index.s3_client')
    def test_handles_quota_exceeded(self, mock_s3):
        """Test handling of storage quota exceeded error."""
        mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': 'QuotaExceeded', 'Message': 'Storage quota exceeded'}},
            'PutObject'
        )

        with pytest.raises(ClientError) as exc_info:
            save_to_s3({'test': 'data'}, 'bucket', 'stats/')

        assert exc_info.value.response['Error']['Code'] == 'QuotaExceeded'

    @patch('data_fetcher_index.s3_client')
    def test_deep_nested_prefix_structure(self, mock_s3):
        """Test deeply nested prefix structure."""
        test_data = {'test': 'data'}
        deep_prefix = 'level1/level2/level3/level4/level5/'

        result = save_to_s3(test_data, 'bucket', deep_prefix)

        assert result.startswith(deep_prefix)
        # Verify S3 was called with correct deep path
        first_call = mock_s3.put_object.call_args_list[0]
        key = first_call[1]['Key']
        assert key.startswith(deep_prefix)
