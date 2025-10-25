from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
)
from constructs import Construct


class FantasyDonStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 Bucket for storing NFL stats data
        stats_bucket = s3.Bucket(
            self,
            "NFLStatsBucket",
            bucket_name=f"nfl-stats-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldStats",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                            transition_after=Duration.days(30),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        ),
                    ],
                )
            ],
        )

        # Data Fetcher Lambda Function (Containerized with nflreadpy)
        # Using Docker container + ARM64 to handle polars dependency (132MB)
        # ARM64 avoids illegal instruction errors from polars' Rust binaries
        data_fetcher_lambda = lambda_.DockerImageFunction(
            self,
            "DataFetcherLambda",
            function_name="nfl-stats-data-fetcher",
            code=lambda_.DockerImageCode.from_image_asset(
                "lambda_functions/data_fetcher",
            ),
            architecture=lambda_.Architecture.ARM_64,
            timeout=Duration.minutes(5),
            memory_size=2048,  # Increased for polars operations
            environment={
                "BUCKET_NAME": stats_bucket.bucket_name,
                "DATA_PREFIX": "stats/",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant S3 write permissions to data fetcher
        stats_bucket.grant_write(data_fetcher_lambda)

        # Data Validator Lambda Function (Containerized)
        # Validates S3 data structure and quality
        data_validator_lambda = lambda_.DockerImageFunction(
            self,
            "DataValidatorLambda",
            function_name="nfl-data-validator",
            code=lambda_.DockerImageCode.from_image_asset(
                "lambda_functions/data_validator",
            ),
            architecture=lambda_.Architecture.ARM_64,
            timeout=Duration.minutes(5),
            memory_size=512,  # Lightweight validation
            environment={
                "BUCKET_NAME": stats_bucket.bucket_name,
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant S3 read/write permissions to validator (needs write for audit reports)
        stats_bucket.grant_read_write(data_validator_lambda)

        # EventBridge Rule to trigger data fetcher daily at 9am UTC (4-5am ET)
        # NFLReadR updates player stats nightly at 3-5am ET, so fetch after processing completes
        daily_rule = events.Rule(
            self,
            "DailyDataFetchRule",
            schedule=events.Schedule.cron(minute="0", hour="9"),
            description="Triggers NFL stats data fetcher daily at 9am UTC (4-5am ET, after NFLReadR nightly update)",
        )
        daily_rule.add_target(targets.LambdaFunction(data_fetcher_lambda))

        # EventBridge Rule to trigger validator daily at 10am UTC (after data fetch)
        validation_rule = events.Rule(
            self,
            "DailyValidationRule",
            schedule=events.Schedule.cron(minute="0", hour="10"),
            description="Triggers data validation daily at 10am UTC (after data fetch)",
        )
        validation_rule.add_target(
            targets.LambdaFunction(
                data_validator_lambda,
                event=events.RuleTargetInput.from_object({
                    "validation_level": "standard",
                    "seasons": [2024, 2025]
                })
            )
        )

        # API Lambda Function
        api_lambda = lambda_.Function(
            self,
            "APILambda",
            function_name="nfl-stats-api",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda_functions/api"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "BUCKET_NAME": stats_bucket.bucket_name,
                "DATA_PREFIX": "stats/",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant S3 read permissions to API lambda
        stats_bucket.grant_read(api_lambda)

        # API Gateway
        api = apigateway.RestApi(
            self,
            "NFLStatsAPI",
            rest_api_name="NFL Stats API",
            description="API for querying NFL statistics",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"],
            ),
        )

        # Lambda integration (proxy mode handles responses automatically)
        lambda_integration = apigateway.LambdaIntegration(api_lambda, proxy=True)

        # API Resources and Methods
        # GET /stats/latest - Get latest stats
        stats_resource = api.root.add_resource("stats")
        latest_resource = stats_resource.add_resource("latest")
        latest_resource.add_method("GET", lambda_integration)

        # GET /stats/season-totals - Get aggregated stats for current season
        season_totals_resource = stats_resource.add_resource("season-totals")
        season_totals_resource.add_method("GET", lambda_integration)

        # GET /stats/{date} - Get stats for specific date
        date_resource = stats_resource.add_resource("{date}")
        date_resource.add_method("GET", lambda_integration)

        # GET /stats/player/{player_id} - Get player-specific stats
        player_resource = stats_resource.add_resource("player")
        player_id_resource = player_resource.add_resource("{player_id}")
        player_id_resource.add_method("GET", lambda_integration)

        # GET /stats/team/{team_id} - Get team-specific stats
        team_resource = stats_resource.add_resource("team")
        team_id_resource = team_resource.add_resource("{team_id}")
        team_id_resource.add_method("GET", lambda_integration)

        # GET /stats/week/{week} - Get stats for specific week
        week_stats_resource = stats_resource.add_resource("week")
        week_number_resource = week_stats_resource.add_resource("{week}")
        week_number_resource.add_method("GET", lambda_integration)

        # GET /stats/season/{season}/week/{week} - Get stats for specific season and week
        season_resource = stats_resource.add_resource("season")
        season_id_resource = season_resource.add_resource("{season}")

        # GET /stats/season/{season}/totals - Get aggregated stats for specific season
        season_totals_resource = season_id_resource.add_resource("totals")
        season_totals_resource.add_method("GET", lambda_integration)

        season_week_resource = season_id_resource.add_resource("week")
        season_week_id_resource = season_week_resource.add_resource("{week}")
        season_week_id_resource.add_method("GET", lambda_integration)

        # GET /week/current - Get current NFL week and season
        week_resource = api.root.add_resource("week")
        current_week_resource = week_resource.add_resource("current")
        current_week_resource.add_method("GET", lambda_integration)

        # Injury endpoints
        injuries_resource = api.root.add_resource("injuries")

        # GET /injuries/current - Get current injury report
        current_injuries_resource = injuries_resource.add_resource("current")
        current_injuries_resource.add_method("GET", lambda_integration)

        # GET /injuries/changes - Get injury status changes
        injury_changes_resource = injuries_resource.add_resource("changes")
        injury_changes_resource.add_method("GET", lambda_integration)

        # GET /injuries/week/{week} - Get injury report for specific week
        injury_week_resource = injuries_resource.add_resource("week")
        injury_week_id_resource = injury_week_resource.add_resource("{week}")
        injury_week_id_resource.add_method("GET", lambda_integration)

        # Games endpoints
        games_resource = api.root.add_resource("games")

        # GET /games/season/{season} - Get all games for a season
        games_season_resource = games_resource.add_resource("season")
        games_season_id_resource = games_season_resource.add_resource("{season}")
        games_season_id_resource.add_method("GET", lambda_integration)

        # CloudFront Distribution for API caching
        # Caches API responses at edge locations to reduce latency and costs
        cache_policy = cloudfront.CachePolicy(
            self,
            "NFLStatsAPICachePolicy",
            cache_policy_name="NFLStatsAPICachePolicy",
            comment="Cache policy for NFL Stats API - 1 hour cache, compress responses",
            default_ttl=Duration.hours(1),  # Data updates daily at midnight UTC
            min_ttl=Duration.minutes(5),
            max_ttl=Duration.hours(24),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
            header_behavior=cloudfront.CacheHeaderBehavior.allow_list("Origin"),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
        )

        distribution = cloudfront.Distribution(
            self,
            "NFLStatsAPIDistribution",
            comment="CloudFront distribution for NFL Stats API",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.RestApiOrigin(
                    api,
                    origin_path="/prod",  # Include the API Gateway stage in origin path
                ),
                cache_policy=cache_policy,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            ),
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # US, Canada, Europe
            enable_logging=False,  # Can enable if needed for analytics
        )

        # Outputs
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "BucketName",
            value=stats_bucket.bucket_name,
            description="S3 bucket for NFL stats data",
        )

        CfnOutput(
            self,
            "ApiEndpoint",
            value=api.url,
            description="API Gateway endpoint URL",
        )

        CfnOutput(
            self,
            "DataFetcherFunctionName",
            value=data_fetcher_lambda.function_name,
            description="Data fetcher Lambda function name",
        )

        CfnOutput(
            self,
            "ApiLambdaFunctionName",
            value=api_lambda.function_name,
            description="API Lambda function name",
        )

        CfnOutput(
            self,
            "DataValidatorFunctionName",
            value=data_validator_lambda.function_name,
            description="Data validator Lambda function name",
        )

        CfnOutput(
            self,
            "CloudFrontURL",
            value=f"https://{distribution.distribution_domain_name}",
            description="CloudFront distribution URL (use this instead of API Gateway URL)",
        )
