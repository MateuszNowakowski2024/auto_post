# 🎨 Social Media Auto-Poster

This repository contains a Python-based automation tool designed to simplify the creation and posting of content to Instagram and Facebook. The script selects images from an S3 bucket, generates captions using OpenAI GPT, and can now also generate engaging slideshow videos for Instagram and Facebook Stories/Reels.

## 🚀 Features

- **Automated Post Generation**  
    Uses OpenAI GPT to generate engaging and relevant captions automatically.

- **Image Selection from AWS S3**  
    Fetches a random, unused image from a specified S3 bucket.

- **Story & Reel Slideshow Generator (New)**  
    - Automatically generates slideshow-style videos optimized for Instagram & Facebook stories/reels.
    - Supports multiple dynamic layouts (two-row, two-column, four-column).
    - Adds customizable text overlays to enhance viewer engagement.
    - Integrates audio tracks for more engaging content.

- **Instagram Posting**  
    Posts photos or generated videos (stories/reels) directly to Instagram using the Meta Graph API.

- **Facebook Posting**  
    Posts photos and videos (stories/reels) to a Facebook Page. Automatically adds comments or links post-publication.

- **Dry-Run Mode**  
    Allows testing the workflow without publishing to social media.

- **GitHub Actions Support**  
    Automatically schedule and run posting scripts using GitHub Actions workflows.

## 🔧 Important Customizations Required

### 1. Update Hardcoded Information

- **gen_post.py:**  
    Customize OpenAI GPT prompts, hashtags, and post descriptions.

- **facebook.py:**  
    Update the hardcoded website link:  
    `"link": "https://lily10coloringbooks.fun"`  
    Replace with your own URL or remove if unnecessary.

### 2. API Keys & Access Tokens

Required environment variables:

```bash
export OPENAI_API_KEY="your-openai-key"
export USER_ACCESS_TOKEN="your-instagram-token"
export IG_ID="your-instagram-id"
export PAGE_ID="your-facebook-page-id"
export PAGE_ACCESS_TOKEN="your-facebook-token"
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export AWS_REGION="your-aws-region"
```

### AWS S3 Bucket Setup

Set up an AWS S3 bucket to store your images/videos with public read permissions to ensure compatibility with Instagram and Facebook's requirements for public image URLs.

## ⚙️ Installation & Setup

### Clone Repository

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Script

#### Photo Posting (Instagram/Facebook):

```bash
python main_photo.py
```

#### Story/Reel Posting (Instagram/Facebook) (New):

```bash
python main_story.py
```

#### Dry-Run Mode:

```bash
python main_story.py --dry-run
```

## 📅 GitHub Actions Automation

### 📹 Story/Reel Workflow

```yaml
name: Daily Story and Reel

on:
    schedule:
        - cron: '0 16 * * *'
    workflow_dispatch:
        inputs:
            dry_run:
                description: "Dry-run mode (no posting)"
                required: false
                default: "false"

jobs:
    post-story:
        runs-on: ubuntu-latest

        steps:
            - uses: actions/checkout@v3
            - uses: actions/setup-python@v4
                with:
                    python-version: '3.11'
            - run: pip install boto3 moviepy==2.0.0.dev2 opencv-python numpy Pillow requests

            - name: Run Story Posting
                env:
                    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
                    PAGE_ID: ${{ secrets.PAGE_ID }}
                    PAGE_ACCESS_TOKEN: ${{ secrets.PAGE_ACCESS_TOKEN }}
                    USER_ACCESS_TOKEN: ${{ secrets.USER_ACCESS_TOKEN }}
                    IG_ID: ${{ secrets.IG_ID }}
                    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
                    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
                    AWS_REGION: ${{ secrets.AWS_REGION }}
                run: |
                    if [ "${{ github.event.inputs.dry_run }}" == "true" ]; then
                        python main_story.py --dry-run
                    else
                        python main_story.py
```

## 📂 Project Structure

```plaintext
.
├── modules/
│   ├── generator.py        # Slideshow Generator for stories/reels *(New)*
│   ├── facebook_photo.py         # Facebook posting functions
│   ├── insta_story.py      # Instagram Story/Reel functions *(New)*
│   ├── facebook_story.py   # Facebook Story/Reel functions *(New)*
│   ├── instagram_photo.py  # Instagram photo posting
│   ├── gen_post_page.py    # Generates posts
│   └── s3.py               # S3 interaction utilities
├── main_photo.py           # Workflow for photo posting
├── main_story.py           # Workflow for stories/reels *(New)*
├── requirements.txt        # Python dependencies
└── README.md               # Documentation
```

## 📜 License

Licensed under the MIT License.
