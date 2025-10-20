# Use AWS Lambda Python ARM64 base image
FROM public.ecr.aws/lambda/python:3.11-arm64

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY index.py ${LAMBDA_TASK_ROOT}/
COPY models.py ${LAMBDA_TASK_ROOT}/
COPY persistence.py ${LAMBDA_TASK_ROOT}/

# Copy calculator modules
COPY calculators/ ${LAMBDA_TASK_ROOT}/calculators/

# Verify files are copied
RUN ls -la ${LAMBDA_TASK_ROOT}/

# Lambda handler
CMD [ "index.handler" ]
