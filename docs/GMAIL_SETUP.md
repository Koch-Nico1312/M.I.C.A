# Gmail API Setup Guide

This guide explains how to set up Gmail API integration for M.I.C.A.

## Prerequisites

1. A Google Account with Gmail enabled
2. Python 3.11 or higher
3. M.I.C.A installed with the Gmail dependencies

## Step 1: Enable Gmail API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** > **Library**
4. Search for "Gmail API" and click on it
5. Click **Enable**

## Step 2: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose **External** user type
   - Fill in the required fields (App name, User support email, etc.)
   - Add **https://www.googleapis.com/auth/gmail.readonly** as a scope
   - Add **https://www.googleapis.com/auth/gmail.send** as a scope
   - Add **https://www.googleapis.com/auth/gmail.modify** as a scope
   - Save and continue
4. Create OAuth client ID:
   - Application type: **Desktop application**
   - Name: **M.I.C.A Gmail**
   - Click **Create**
5. Download the JSON file (it will be named something like `credentials.json`)

## Step 3: Configure M.I.C.A

1. Rename the downloaded JSON file to `gmail_credentials.json`
2. Move it to the `config/` directory in your M.I.C.A installation:
   ```
   mv ~/Downloads/credentials.json /path/to/M.I.C.A/config/gmail_credentials.json
   ```
3. Enable Gmail in your configuration:

   **Option A: Using .env file**
   ```bash
   # Edit .env
   GMAIL_ENABLED=true
   ```

   **Option B: Using config.yaml**
   ```yaml
   gmail:
     enabled: true
     credentials_path: "./config/gmail_credentials.json"
     token_path: "./config/gmail_token.json"
   ```

## Step 4: Authenticate

The first time you use Gmail features, M.I.C.A will open a browser window asking you to:

1. Sign in to your Google Account
2. Grant permission to M.I.C.A to access your Gmail
3. The authentication token will be saved automatically

After successful authentication, you won't need to repeat this step.

## Usage Examples

Once configured, you can use Gmail features with voice commands:

### List Emails
```
"M.I.C.A, list my emails"
"M.I.C.A, show me the last 5 emails"
"M.I.C.A, list emails from John"
```

### Read Email
```
"M.I.C.A, read the email with ID 12345"
"M.I.C.A, show me the full email"
```

### Send Email
```
"M.I.C.A, send an email to john@example.com"
"M.I.C.A, email Sarah about the meeting"
```

### Reply to Email
```
"M.I.C.A, reply to that email"
"M.I.C.A, reply saying I'll be there"
```

### Search Emails
```
"M.I.C.A, search for emails about project X"
"M.I.C.A, find emails from last week"
```

### Get Unread Count
```
"M.I.C.A, how many unread emails do I have?"
```

### Mark as Read
```
"M.I.C.A, mark that email as read"
```

### Archive Email
```
"M.I.C.A, archive that email"
```

### Delete Email
```
"M.I.C.A, delete that email"
```

### Summarize Emails
```
"M.I.C.A, summarize my recent emails"
"M.I.C.A, give me a summary of important emails"
```

## Available Actions

The `gmail_manager` tool supports the following actions:

- **list**: List emails from inbox or other labels
- **read**: Read full email content
- **send**: Send a new email
- **reply**: Reply to an existing email
- **search**: Search emails using Gmail search syntax
- **unread_count**: Get count of unread emails
- **mark_read**: Mark an email as read
- **archive**: Archive an email
- **delete**: Delete an email
- **summarize**: Summarize recent emails

## Security Notes

- The `gmail_credentials.json` file contains sensitive OAuth credentials
- Never commit this file to version control
- The `gmail_token.json` file contains your authentication token
- Both files should be kept secure and private

## Troubleshooting

### "No credentials file found"
- Ensure `gmail_credentials.json` is in the `config/` directory
- Check that the file path in config.yaml is correct

### "Authentication failed"
- Make sure you've enabled the Gmail API in Google Cloud Console
- Verify the OAuth consent screen is properly configured
- Try deleting `gmail_token.json` and re-authenticating

### "API quota exceeded"
- Gmail API has daily usage limits
- Wait until the quota resets or request a higher quota

### "Permission denied"
- Ensure the correct scopes are enabled in OAuth consent screen
- Re-authenticate if you've changed the scopes

## Gmail Search Syntax

You can use Gmail's powerful search syntax:

- `from:john@example.com` - Emails from John
- `to:me` - Emails sent to you
- `subject:meeting` - Emails with "meeting" in subject
- `has:attachment` - Emails with attachments
- `is:unread` - Unread emails
- `is:starred` - Starred emails
- `after:2024/01/01` - Emails after a date
- `before:2024/12/31` - Emails before a date
- `label:important` - Emails with specific label

## Advanced Configuration

### Custom Labels
```python
# List emails from a specific label
gmail_manager({
    "action": "list",
    "label": "IMPORTANT",
    "max_results": 20
})
```

### Search with Query
```python
# Search with complex query
gmail_manager({
    "action": "search",
    "query": "from:boss@example.com is:unread",
    "max_results": 10
})
```

### Send with CC/BCC
```python
# Send email with CC and BCC
gmail_manager({
    "action": "send",
    "to": "recipient@example.com",
    "cc": "cc@example.com",
    "bcc": "bcc@example.com",
    "subject": "Meeting Update",
    "body": "The meeting is confirmed for tomorrow."
})
```

## Privacy

- M.I.C.A only accesses your Gmail when you explicitly request it
- Email content is processed locally when possible
- No data is stored permanently by M.I.C.A
- You can revoke access at any time from Google Account settings

## Support

For issues or questions:
- Check the Google Cloud Console for API errors
- Verify your credentials file is correctly formatted
- Ensure all dependencies are installed
- Check the M.I.C.A logs for error messages
