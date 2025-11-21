# Zing Blog Generation Service

Automated blog content generation and Duda API integration service. This service generates SEO-optimized blog posts using OpenAI's GPT-4 and publishes them directly to Duda websites.

## Features

- 🤖 **AI-Powered Content**: Generate professional blog posts using OpenAI GPT-4
- 📝 **SEO Optimized**: Built-in SEO guidelines and best practices
- 🎯 **Industry & Location Aware**: Contextual content based on business type and location
- 🔄 **Batch Generation**: Generate 12 unique blogs per request
- 🚀 **Duda Integration**: Direct API integration with Duda platform
- 🔧 **Flexible Deployment**: Local and production modes for testing and deployment
- 💻 **Simple UI**: Web interface for manual blog generation
- ⚙️ **Easy Configuration**: Non-engineer friendly YAML configuration

## Architecture

```
zing-blog-post-service/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── schemas.py           # Pydantic data models
│   ├── api/
│   │   └── routes.py        # API endpoints
│   ├── services/
│   │   ├── blog_generator.py   # OpenAI integration
│   │   ├── html_formatter.py   # HTML formatting & base64 encoding
│   │   └── duda_client.py      # Duda API client
│   └── templates/
│       └── index.html       # Web UI
├── config.yaml              # Application configuration
├── .env                     # Environment variables (create from .env.example)
└── requirements.txt         # Python dependencies
```

## Setup Instructions

### 1. Prerequisites

- Python 3.9 or higher
- OpenAI API key
- Duda API credentials (user/password)

### 2. Installation

```bash
# Clone or navigate to the project directory
cd zing-blog-post-service

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

#### Environment Variables

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
OPENAI_API_KEY=your_openai_api_key_here
DUDA_API_USER=your_duda_api_user
DUDA_API_PASSWORD=your_duda_api_password
ENVIRONMENT=development
```

#### Application Configuration

Edit `config.yaml` to customize blog generation settings:

```yaml
blog_generation:
  model: "gpt-4"              # OpenAI model to use
  temperature: 0.7            # Creativity level (0.0-1.0)
  word_count_min: 1300        # Minimum words per blog
  word_count_max: 1600        # Maximum words per blog
  tone: "professional"        # Writing tone
  number_of_blogs: 12         # Blogs to generate per request

deployment:
  mode: "local"               # "local" or "production"
  host: "0.0.0.0"
  port: 8000
```

### 4. Running the Service

```bash
# Start the FastAPI server
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The service will be available at:
- Web UI: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Usage

### Web Interface

1. Open http://localhost:8000 in your browser
2. Select a tenant from the dropdown
3. Review the tenant information
4. Click "Generate & Send Blogs"
5. Wait for generation to complete (may take several minutes)
6. Review the results

### API Endpoints

#### Generate Blogs

```bash
POST /generate
Content-Type: application/json

{
  "tenant_id": "tenant_001"
}
```

Response:
```json
{
  "message": "Generated 12 blogs, sent 12 to Duda",
  "tenant_id": "tenant_001",
  "business_name": "Acme Plumbing Services",
  "blogs_generated": 12,
  "blogs_sent_to_duda": 12,
  "success": true,
  "errors": [],
  "details": [
    {
      "blog_number": 1,
      "title": "Top 10 Plumbing Tips...",
      "success": true
    }
  ]
}
```

#### Get All Tenants

```bash
GET /tenants
```

#### Get Specific Tenant

```bash
GET /tenants/{tenant_id}
```

#### Health Check

```bash
GET /health
```

#### View Configuration

```bash
GET /config
```

#### Reload Configuration

```bash
POST /config/reload
```

## Testing Phase

During the testing phase, tenant data is **hardcoded** in `app/config.py`:

```python
HARDCODED_TENANTS = {
    "tenant_001": {
        "tenant_id": "tenant_001",
        "business_name": "Acme Plumbing Services",
        "industry": "Plumbing",
        "location": "Austin, Texas",
        "duda_site_code": "example-site-001"
    },
    # Add more test tenants as needed
}
```

To add test tenants, edit the `HARDCODED_TENANTS` dictionary in `app/config.py`.

## Deployment Modes

### Local Mode

- **Purpose**: Testing and development
- **Configuration**: Set `mode: "local"` in `config.yaml`
- **Behavior**: Sends blogs directly to Duda API using credentials from `.env`

### Production Mode

- **Purpose**: Integration with existing infrastructure
- **Configuration**: Set `mode: "production"` in `config.yaml`
- **Behavior**: Invokes separate Duda Integration Service
- **Note**: Requires Duda Integration Service endpoint configuration in `app/services/duda_client.py`

## Database Integration (Future)

The service is designed to integrate with PostgreSQL for tenant management. Database-related code is currently commented out in `requirements.txt`.

When ready to integrate:

1. Uncomment database dependencies in `requirements.txt`:
   ```txt
   sqlalchemy==2.0.23
   psycopg2-binary==2.9.9
   alembic==1.12.1
   ```

2. Create database models and migrations

3. Update `get_tenant_data()` function in `app/config.py` to query the database

4. Add `DATABASE_URL` to `.env`

## Blog Output Format

Each blog is formatted as:

1. **HTML Document**: Complete HTML with semantic structure
2. **Base64 Encoded**: Encoded for Duda API compatibility
3. **Duda Payload**:
   ```json
   {
     "title": "Blog title (60-70 chars)",
     "description": "Meta description (150-160 chars)",
     "content": "base64_encoded_html_content",
     "author": "Business Name"
   }
   ```

## Troubleshooting

### OpenAI API Errors

- Verify your API key in `.env`
- Check your OpenAI account has sufficient credits
- Ensure `gpt-4` access is enabled on your account

### Duda API Errors

- Verify Duda credentials in `.env`
- Check the `duda_site_code` is correct
- Ensure your Duda API account has blog post import permissions

### Configuration Changes Not Applied

- Restart the service after modifying `config.yaml`
- Or use the `/config/reload` endpoint to reload without restart

### Import Errors

- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again

## API Rate Limiting

- OpenAI: GPT-4 has rate limits depending on your account tier
- Duda: Check your Duda API rate limits

The service sends blogs sequentially to avoid overwhelming the APIs.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests (when test suite is created)
pytest
```

### Code Structure

- **app/main.py**: FastAPI application setup
- **app/config.py**: Configuration and hardcoded test data
- **app/schemas.py**: Pydantic models for validation
- **app/api/routes.py**: API endpoint definitions
- **app/services/blog_generator.py**: OpenAI integration logic
- **app/services/html_formatter.py**: HTML/base64 formatting
- **app/services/duda_client.py**: Duda API client

## Future Enhancements

- [ ] PostgreSQL database integration
- [ ] Background job processing with Celery
- [ ] Webhook notifications for completion
- [ ] Blog preview before sending
- [ ] Scheduled automatic generation
- [ ] Analytics and reporting
- [ ] Multi-language support
- [ ] Custom prompt templates per industry

## Support

For issues or questions:
1. Check the logs in the terminal where the service is running
2. Verify configuration in `config.yaml` and `.env`
3. Test API endpoints using the built-in docs at `/docs`

## License

[Add your license information here]
