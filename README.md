# **Social Media Auto-Poster**  

This repository contains a **Python-based automation script** that generates and posts content to **Instagram and Facebook**. The script selects a random coloring book cover image from an **S3 bucket**, generates a caption using **OpenAI GPT**, and posts it to social media.  

---

## **Features**
- ✅ **Automated Post Generation**: Uses OpenAI GPT to generate engaging captions.  
- 🖼️ **S3 Image Selection**: Selects a new, unused image from an S3 bucket.  
- 📸 **Instagram Posting**: Uploads the image and caption to Instagram via the Graph API.  
- 🏷️ **Facebook Posting**: Posts to a Facebook Page with a follow-up comment.  
- ⚡ **Dry-Run Mode**: Allows testing the workflow without actually posting.  
- ⏳ **GitHub Actions Support**: Can be scheduled to run automatically.  

---

## **Important Customization Required**
### **1. Hardcoded Information in Scripts**
Some parts of the script contain **hardcoded values** that must be adjusted before running:
- **`gen_post.py`**:
    - The **OpenAI GPT prompts** for generating captions.
    - Adjust wording, hashtags, and descriptions as needed.

- **`facebook.py`**:
    - The **hardcoded website link** in the comment post:
        ```python
        "link": "https://lily10coloringbooks.fun"
        ```
    - Modify this to your own website or remove it if not needed.

### **2. API Keys & Access Tokens**
The script requires API keys and access tokens for OpenAI, Instagram, and Facebook.
- **Environment Variables Required**:
    ```bash
    export OPENAI_API_KEY="your-openai-key"
    export USER_ACCESS_TOKEN="your-instagram-token"
    export IG_ID="your-instagram-id"
    export PAGE_ID="your-facebook-page-id"
    export PAGE_ACCESS_TOKEN="your-facebook-token"
    ```

💬 Need help acquiring access tokens or IDs? Drop a comment or DM me, and I'll guide you through the process.

---

## **Requirements**
1. **AWS S3 Bucket for Images**  
     The project requires an S3 bucket containing images that have public URLs.  
     This is necessary because Meta's Instagram and Facebook APIs require public image URLs for posting.  
     Ensure that your S3 bucket allows public access to images.

---

## **Installation & Setup**
1. **Clone the Repository**
     ```bash
     git clone https://github.com/your-username/your-repo.git
     cd your-repo
     ```

2. **Install Dependencies**
     ```bash
     pip install -r requirements.txt
     ```

3. **Run the Script**
     - **Live Mode (posts to Instagram & Facebook)**:
         ```bash
         python main.py
         ```
     - **Dry-Run Mode (test without posting)**:
         ```bash
         python main.py --dry-run
         ```

---

## **GitHub Actions Automation**
The script can be scheduled to run automatically using GitHub Actions.  
Modify `.github/workflows/posting.yml` to adjust the posting schedule.

Example workflow file (`.github/workflows/posting.yml`):
```yaml
name: Social Media Posting Workflow

on:
    workflow_dispatch:  # Allows manual triggering from GitHub Actions UI
    schedule:
        - cron: '0 12 * * *'  # Runs every day at 12 PM UTC (adjust as needed)

jobs:
    post:
        runs-on: ubuntu-latest

        steps:
            - name: Checkout repository
                uses: actions/checkout@v3

            - name: Set up Python
                uses: actions/setup-python@v4
                with:
                    python-version: '3.9'  # Adjust to match your script's Python version

            - name: Install dependencies
                run: pip install -r requirements.txt

            - name: Run the script in DRY RUN mode
                run: python main.py --dry-run
```

To enable live posting, modify the last step:
```yaml
            - name: Run the script in Live Mode
                run: python main.py
```

---

## **File Structure**
```
├── gen_post.py        # Generates image URL and caption
├── instagram.py       # Posts to Instagram
├── facebook.py        # Posts to Facebook
├── main.py            # Orchestrates the workflow
├── requirements.txt   # Required dependencies
├── .github/workflows/ # GitHub Actions for automation
└── README.md          # Project documentation
```

---

## **License**
This project is licensed under the MIT License.