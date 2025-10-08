import json
import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import sys
import os

# Add lambda functions to path and import using importlib to avoid conflicts
import importlib.util

api_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../lambda_functions/api/index.py')
)

spec = importlib.util.spec_from_file_location("api_index", api_path)
api_module = importlib.util.module_from_spec(spec)
sys.modules['api_index'] = api_module  # Register in sys.modules for @patch
spec.loader.exec_module(api_module)

get_latest_stats = api_module.get_latest_stats
get_stats_by_date = api_module.get_stats_by_date
filter_player_stats = api_module.filter_player_stats
filter_team_stats = api_module.filter_team_stats
handler = api_module.handler


class TestGetLatestStats:
    """Test suite for retrieving latest stats from S3."""

    @patch('api_index.s3_client')
    def test_retrieves_latest_json(self, mock_s3):
        """Test that get_latest_stats retrieves the latest.json file."""
        mock_data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'players': [{'id': 1, 'name': 'Player 1'}],
                'teams': [],
                'games': []
            }
        }

        mock_response = {
            'Body': Mock(read=lambda: json.dumps(mock_data).encode('utf-8'))
        }
        mock_s3.get_object.return_value = mock_response

        result = get_latest_stats('test-bucket', 'stats/')

        # Verify correct S3 call
        mock_s3.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='stats/latest.json'
        )

        # Verify returned data
        assert result == mock_data

    @patch('api_index.s3_client')
    def test_returns_none_when_file_not_found(self, mock_s3):
        """Test that None is returned when latest.json doesn't exist."""
        mock_s3.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}},
            'GetObject'
        )

        result = get_latest_stats('test-bucket', 'stats/')

        assert result is None

    @patch('api_index.s3_client')
    def test_handles_access_denied(self, mock_s3):
        """Test that AccessDenied errors are raised."""
        mock_s3.get_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'GetObject'
        )

        with pytest.raises(ClientError) as exc_info:
            get_latest_stats('test-bucket', 'stats/')

        assert exc_info.value.response['Error']['Code'] == 'AccessDenied'

    @patch('api_index.s3_client')
    def test_handles_bucket_not_found(self, mock_s3):
        """Test handling when bucket doesn't exist."""
        mock_s3.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket', 'Message': 'Bucket not found'}},
            'GetObject'
        )

        with pytest.raises(ClientError):
            get_latest_stats('nonexistent-bucket', 'stats/')

    @patch('api_index.s3_client')
    def test_parses_json_correctly(self, mock_s3):
        """Test that JSON is correctly parsed from S3 response."""
        complex_data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'players': [
                    {'id': 1, 'name': 'Player 1', 'stats': {'yards': 100}},
                    {'id': 2, 'name': 'Player 2', 'stats': {'yards': 200}}
                ],
                'teams': [{'id': 'KC', 'name': 'Chiefs'}],
                'games': []
            },
            'metadata': {'season': 2025}
        }

        mock_response = {
            'Body': Mock(read=lambda: json.dumps(complex_data).encode('utf-8'))
        }
        mock_s3.get_object.return_value = mock_response

        result = get_latest_stats('bucket', 'stats/')

        assert result == complex_data
        assert len(result['data']['players']) == 2
        assert result['data']['players'][0]['stats']['yards'] == 100

    @patch('api_index.s3_client')
    def test_handles_malformed_json(self, mock_s3):
        """Test handling of malformed JSON in S3."""
        mock_response = {
            'Body': Mock(read=lambda: b'{invalid json')
        }
        mock_s3.get_object.return_value = mock_response

        with pytest.raises(json.JSONDecodeError):
            get_latest_stats('bucket', 'stats/')

    @patch('api_index.s3_client')
    def test_uses_correct_prefix(self, mock_s3):
        """Test that the correct prefix is used in S3 key."""
        mock_response = {
            'Body': Mock(read=lambda: json.dumps({}).encode('utf-8'))
        }
        mock_s3.get_object.return_value = mock_response

        # Test with different prefixes
        get_latest_stats('bucket', 'custom-prefix/')
        mock_s3.get_object.assert_called_with(
            Bucket='bucket',
            Key='custom-prefix/latest.json'
        )

        mock_s3.reset_mock()

        get_latest_stats('bucket', '')
        mock_s3.get_object.assert_called_with(
            Bucket='bucket',
            Key='latest.json'
        )


class TestGetStatsByDate:
    """Test suite for retrieving stats by specific date."""

    @patch('api_index.s3_client')
    def test_retrieves_stats_for_valid_date(self, mock_s3):
        """Test retrieving stats for a specific date."""
        mock_data = {'timestamp': '2025-10-01T12:00:00Z', 'data': {}}

        # Mock list_objects_v2 response
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'stats/2025/10/01/12-00-00.json', 'LastModified': datetime(2025, 10, 1, 12, 0, 0)}
            ]
        }

        # Mock get_object response
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: json.dumps(mock_data).encode('utf-8'))
        }

        result = get_stats_by_date('test-bucket', 'stats/', '2025-10-01')

        # Verify list_objects was called with correct prefix
        mock_s3.list_objects_v2.assert_called_once_with(
            Bucket='test-bucket',
            Prefix='stats/2025/10/01/'
        )

        # Verify get_object was called
        mock_s3.get_object.assert_called_once()

        assert result == mock_data

    @patch('api_index.s3_client')
    def test_returns_none_when_no_data_for_date(self, mock_s3):
        """Test that None is returned when no data exists for the date."""
        # Empty Contents
        mock_s3.list_objects_v2.return_value = {}

        result = get_stats_by_date('test-bucket', 'stats/', '2025-10-01')

        assert result is None

    @patch('api_index.s3_client')
    def test_returns_most_recent_file_for_date(self, mock_s3):
        """Test that the most recent file is returned when multiple exist."""
        # Multiple files for the same date
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'stats/2025/10/01/10-00-00.json', 'LastModified': datetime(2025, 10, 1, 10, 0, 0)},
                {'Key': 'stats/2025/10/01/15-30-00.json', 'LastModified': datetime(2025, 10, 1, 15, 30, 0)},
                {'Key': 'stats/2025/10/01/12-00-00.json', 'LastModified': datetime(2025, 10, 1, 12, 0, 0)}
            ]
        }

        mock_data = {'timestamp': '2025-10-01T15:30:00Z'}
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: json.dumps(mock_data).encode('utf-8'))
        }

        result = get_stats_by_date('test-bucket', 'stats/', '2025-10-01')

        # Should retrieve the 15:30:00 file (most recent)
        mock_s3.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='stats/2025/10/01/15-30-00.json'
        )

    @patch('api_index.s3_client')
    def test_handles_invalid_date_format(self, mock_s3):
        """Test that invalid date format raises ValueError."""
        with pytest.raises(ValueError):
            get_stats_by_date('bucket', 'stats/', 'invalid-date')

        with pytest.raises(ValueError):
            get_stats_by_date('bucket', 'stats/', '2025/10/01')

        with pytest.raises(ValueError):
            get_stats_by_date('bucket', 'stats/', '10-01-2025')

    @patch('api_index.s3_client')
    def test_handles_future_dates(self, mock_s3):
        """Test querying for future dates (should return None if no data)."""
        mock_s3.list_objects_v2.return_value = {}

        result = get_stats_by_date('bucket', 'stats/', '2030-12-31')

        assert result is None

    @patch('api_index.s3_client')
    def test_handles_list_objects_error(self, mock_s3):
        """Test handling of list_objects_v2 errors."""
        mock_s3.list_objects_v2.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'ListObjectsV2'
        )

        with pytest.raises(ClientError):
            get_stats_by_date('bucket', 'stats/', '2025-10-01')


class TestFilterPlayerStats:
    """Test suite for filtering player-specific stats."""

    def test_filters_player_by_id(self):
        """Test filtering player by ID."""
        data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'players': [
                    {'id': '123', 'name': 'Player A', 'stats': {'yards': 100}},
                    {'id': '456', 'name': 'Player B', 'stats': {'yards': 200}}
                ]
            },
            'metadata': {'season': 2025}
        }

        result = filter_player_stats(data, '123')

        assert result is not None
        assert result['player']['id'] == '123'
        assert result['player']['name'] == 'Player A'
        assert result['timestamp'] == data['timestamp']
        assert result['metadata'] == data['metadata']

    def test_filters_player_by_name_case_insensitive(self):
        """Test filtering player by name (case insensitive)."""
        data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'players': [
                    {'id': '123', 'name': 'Patrick Mahomes', 'stats': {'yards': 300}}
                ]
            },
            'metadata': {}
        }

        result = filter_player_stats(data, 'patrick mahomes')

        assert result is not None
        assert result['player']['name'] == 'Patrick Mahomes'

        # Test different case
        result2 = filter_player_stats(data, 'PATRICK MAHOMES')
        assert result2 is not None

    def test_returns_none_when_player_not_found(self):
        """Test that None is returned when player doesn't exist."""
        data = {
            'data': {
                'players': [
                    {'id': '123', 'name': 'Player A'}
                ]
            }
        }

        result = filter_player_stats(data, '999')

        assert result is None

    def test_handles_empty_players_list(self):
        """Test handling of empty players list."""
        data = {
            'data': {
                'players': []
            }
        }

        result = filter_player_stats(data, '123')

        assert result is None

    def test_handles_missing_players_key(self):
        """Test handling when 'players' key is missing."""
        data = {
            'data': {}
        }

        result = filter_player_stats(data, '123')

        assert result is None

    def test_filters_first_match_only(self):
        """Test that only the first matching player is returned."""
        data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'players': [
                    {'id': '123', 'name': 'Player A', 'team': 'KC'},
                    {'id': '123', 'name': 'Player A', 'team': 'SF'}  # Duplicate
                ]
            },
            'metadata': {}
        }

        result = filter_player_stats(data, '123')

        assert result['player']['team'] == 'KC'  # First match


class TestFilterTeamStats:
    """Test suite for filtering team-specific stats."""

    def test_filters_team_by_id(self):
        """Test filtering team by ID."""
        data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'teams': [
                    {'id': 'KC', 'name': 'Kansas City Chiefs', 'abbreviation': 'KC'},
                    {'id': 'SF', 'name': 'San Francisco 49ers', 'abbreviation': 'SF'}
                ]
            },
            'metadata': {}
        }

        result = filter_team_stats(data, 'KC')

        assert result is not None
        assert result['team']['id'] == 'KC'
        assert result['team']['name'] == 'Kansas City Chiefs'

    def test_filters_team_by_abbreviation(self):
        """Test filtering team by abbreviation (case insensitive)."""
        data = {
            'data': {
                'teams': [
                    {'id': '1', 'abbreviation': 'KC', 'name': 'Kansas City Chiefs'}
                ]
            },
            'metadata': {}
        }

        result = filter_team_stats(data, 'kc')

        assert result is not None
        assert result['team']['abbreviation'] == 'KC'

    def test_filters_team_by_name(self):
        """Test filtering team by name (case insensitive)."""
        data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'teams': [
                    {'id': '1', 'name': 'Kansas City Chiefs', 'abbreviation': 'KC'}
                ]
            },
            'metadata': {}
        }

        result = filter_team_stats(data, 'kansas city chiefs')

        assert result is not None
        assert result['team']['name'] == 'Kansas City Chiefs'

        # Test partial match
        result2 = filter_team_stats(data, 'chiefs')
        assert result2 is None  # Exact match required

    def test_returns_none_when_team_not_found(self):
        """Test that None is returned when team doesn't exist."""
        data = {
            'data': {
                'teams': [
                    {'id': 'KC', 'name': 'Kansas City Chiefs', 'abbreviation': 'KC'}
                ]
            }
        }

        result = filter_team_stats(data, 'DAL')

        assert result is None

    def test_handles_empty_teams_list(self):
        """Test handling of empty teams list."""
        data = {
            'data': {
                'teams': []
            }
        }

        result = filter_team_stats(data, 'KC')

        assert result is None


class TestAPIHandlerS3Queries:
    """Test suite for API handler S3 query operations."""

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('api_index.get_latest_stats')
    def test_latest_endpoint_queries_s3(self, mock_get_latest):
        """Test that /stats/latest endpoint queries S3."""
        mock_data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {'players': [], 'teams': [], 'games': []}
        }
        mock_get_latest.return_value = mock_data

        event = {
            'httpMethod': 'GET',
            'path': '/stats/latest',
            'pathParameters': {}
        }

        result = handler(event, None)

        # Verify S3 query was made
        mock_get_latest.assert_called_once_with('test-bucket', 'stats/')

        # Verify response
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body == mock_data

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('api_index.get_latest_stats')
    def test_latest_endpoint_handles_no_data(self, mock_get_latest):
        """Test /stats/latest when no data exists in S3."""
        mock_get_latest.return_value = None

        event = {
            'httpMethod': 'GET',
            'path': '/stats/latest',
            'pathParameters': {}
        }

        result = handler(event, None)

        assert result['statusCode'] == 404
        body = json.loads(result['body'])
        assert 'error' in body
        assert 'No stats data available' in body['error']

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('api_index.get_stats_by_date')
    def test_date_endpoint_queries_s3(self, mock_get_by_date):
        """Test that /stats/{date} endpoint queries S3."""
        mock_data = {
            'timestamp': '2025-10-01T12:00:00Z',
            'data': {}
        }
        mock_get_by_date.return_value = mock_data

        event = {
            'httpMethod': 'GET',
            'path': '/stats/2025-10-01',
            'pathParameters': {'date': '2025-10-01'}
        }

        result = handler(event, None)

        # Verify S3 query was made with correct date
        mock_get_by_date.assert_called_once_with('test-bucket', 'stats/', '2025-10-01')

        assert result['statusCode'] == 200

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('api_index.get_stats_by_date')
    def test_date_endpoint_handles_no_data(self, mock_get_by_date):
        """Test /stats/{date} when no data exists for that date."""
        mock_get_by_date.return_value = None

        event = {
            'httpMethod': 'GET',
            'path': '/stats/2025-10-01',
            'pathParameters': {'date': '2025-10-01'}
        }

        result = handler(event, None)

        assert result['statusCode'] == 404
        body = json.loads(result['body'])
        assert 'No stats found for date' in body['error']

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('api_index.get_latest_stats')
    def test_player_endpoint_queries_s3_and_filters(self, mock_get_latest):
        """Test that /stats/player/{player_id} queries S3 and filters."""
        mock_data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'players': [
                    {'id': '123', 'name': 'Player A'},
                    {'id': '456', 'name': 'Player B'}
                ]
            },
            'metadata': {}
        }
        mock_get_latest.return_value = mock_data

        event = {
            'httpMethod': 'GET',
            'path': '/stats/player/123',
            'pathParameters': {'player_id': '123'}
        }

        result = handler(event, None)

        # Verify S3 query
        mock_get_latest.assert_called_once_with('test-bucket', 'stats/')

        # Verify filtering
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['player']['id'] == '123'

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('api_index.get_latest_stats')
    def test_player_endpoint_handles_player_not_found(self, mock_get_latest):
        """Test /stats/player/{player_id} when player doesn't exist."""
        mock_data = {
            'data': {
                'players': [
                    {'id': '123', 'name': 'Player A'}
                ]
            }
        }
        mock_get_latest.return_value = mock_data

        event = {
            'httpMethod': 'GET',
            'path': '/stats/player/999',
            'pathParameters': {'player_id': '999'}
        }

        result = handler(event, None)

        assert result['statusCode'] == 404
        body = json.loads(result['body'])
        assert 'Player 999 not found' in body['error']

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'DATA_PREFIX': 'stats/'})
    @patch('api_index.get_latest_stats')
    def test_team_endpoint_queries_s3_and_filters(self, mock_get_latest):
        """Test that /stats/team/{team_id} queries S3 and filters."""
        mock_data = {
            'timestamp': '2025-10-04T12:00:00Z',
            'data': {
                'teams': [
                    {'id': 'KC', 'name': 'Kansas City Chiefs', 'abbreviation': 'KC'},
                    {'id': 'SF', 'name': 'San Francisco 49ers', 'abbreviation': 'SF'}
                ]
            },
            'metadata': {}
        }
        mock_get_latest.return_value = mock_data

        event = {
            'httpMethod': 'GET',
            'path': '/stats/team/KC',
            'pathParameters': {'team_id': 'KC'}
        }

        result = handler(event, None)

        # Verify S3 query
        mock_get_latest.assert_called_once_with('test-bucket', 'stats/')

        # Verify filtering
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['team']['id'] == 'KC'

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket'})
    @patch('api_index.get_latest_stats')
    def test_handles_s3_access_errors(self, mock_get_latest):
        """Test handling of S3 access errors."""
        mock_get_latest.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'GetObject'
        )

        event = {
            'httpMethod': 'GET',
            'path': '/stats/latest',
            'pathParameters': {}
        }

        result = handler(event, None)

        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert 'error' in body

    @patch.dict(os.environ, {})
    def test_handles_missing_bucket_env_var(self):
        """Test error when BUCKET_NAME is not set."""
        event = {
            'httpMethod': 'GET',
            'path': '/stats/latest',
            'pathParameters': {}
        }

        result = handler(event, None)

        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert 'BUCKET_NAME' in body['error']
