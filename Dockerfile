# FROM python:3.9-slim

# # Set the working directory in the container to /app
# WORKDIR /app

# RUN apt-get update && apt-get install -y \
#     gcc \
#     default-libmysqlclient-dev \
#     pkg-config \
#     netcat-openbsd

# # Copy the requirements.txt file into the container at /app
# COPY requirements.txt /app

# # Install any needed packages specified in requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

FROM princebutani/backend_requirements

WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Pass the environment variable from your host to the Docker build process
ARG OPENAI_API_KEY

# Echo the environment variable value into the .env file
RUN echo "OPENAI_API_KEY=$OPENAI_API_KEY" > .env

# Make port 5000 available to the world outside this container
EXPOSE 5000

RUN "python test_app.py"

CMD ["python", "app.py"]