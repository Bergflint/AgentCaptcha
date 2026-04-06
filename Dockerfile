# Use an official lightweight Python image
FROM python:3.11

# Set the working directory to /code
WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libx11-dev \
    libxcomposite-dev \
    libxrandr-dev \
    libasound2-dev \
    libappindicator3-1 \
    libnspr4 \
    libnss3 \
    wget \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    libxss1 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxtst6 \
    libnss3 \
    fonts-liberation \
    libappindicator3-1 \
    libxrandr2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libgbm1 \
    libasound2 \
    xdg-utils \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# Install Playwright
RUN pip install playwright

# Install Playwright browsers (Chromium, Firefox, WebKit)
RUN playwright install --with-deps

# Copy Pipfile and Pipfile.lock to install dependencies (to leverage Docker caching)
COPY Pipfile Pipfile.lock /code/

# Install pipenv and project dependencies
RUN pip install pipenv && pipenv install --deploy --system --dev

# Copy the rest of the application code
COPY . /code

# Set working directory back to /code
WORKDIR /code

# Workaround for setuptools bug
RUN echo "setuptools<72" > constraints.txt
ENV PIP_CONSTRAINT=constraints.txt

# Expose port 8001 for your web application
EXPOSE 8001

# Command to run the Django application using Daphne
CMD sh -c "python manage.py collectstatic --noinput && daphne -b 0.0.0.0 -p $PORT agentapps.asgi:application"
