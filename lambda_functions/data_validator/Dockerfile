# Use AWS Lambda Python ARM64 base image
FROM public.ecr.aws/lambda/python:3.11-arm64

# Copy requirements and install dependencies (none currently needed)
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY index.py ${LAMBDA_TASK_ROOT}/
COPY validators.py ${LAMBDA_TASK_ROOT}/
COPY schema.py ${LAMBDA_TASK_ROOT}/

# Verify files are copied
RUN ls -la ${LAMBDA_TASK_ROOT}/

# Lambda handler
CMD [ "index.handler" ]
# Force rebuild 2025-10-08-playoff-week-thresholds
