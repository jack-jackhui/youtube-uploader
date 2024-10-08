# YouTube & Instagram & Chinese Social Platforms (XHS, Douyin, etc.) Video Upload Project

This project automates the process of uploading videos to YouTube and Instagram using the YouTube Data API v3 and Facebook Graph API v20.0. It handles OAuth 2.0 authentication, video upload, and management of YouTube/Instagram video metadata.
Also supports Chinese social media platform such as XHS, Douyin, etc. 

## Features

- **OAuth 2.0 Authentication**: Handles Google account authentication automatically using refresh tokens.
- **Video Upload**: Uploads videos to a specified YouTube account.
- **Metadata Management**: Allows specification of video metadata such as title, description, tags, and category.
- **Integrate with GenAI** for automated video generation. Check out this <a href="https://ai-video.jackhui.com.au">project</a> for details.
- **Instagram Video Upload**: Also supports video uploading to Instagram.
- **Chinese Social Platform Video Upload**: Also supports video uploading to Chinese social platforms such xhs, douyin, etc.

## Prerequisites

Before you begin, ensure you have met the following requirements:
- You have a `Python 3.x` environment.
- You have a Google account with access to the YouTube Data API.
- You have set up a project in the Google Developers Console and have credentials in the form of a `client_secrets.json` file.
- Create a .env.production file under the project root and provide SMTP credential if you intend to use the email notification feature.
- Also provide LLM(e.g. OpenAI) API key if intend to use AI generated topic for videos.
- Instagram reels video upload requires Facebook Graph API key and Instagram User ID. Check Facebook developer documentation for details.
- Provision the api keys and other details using the format in the example.env file
- For Chinese social platform, prepare a cookies folder under the project root. Download the respective cookies files under cookies/bili_cookies.json,cookies/xhs_cookies.json,cookies/douyin_cookies.json

## Installation

To install the necessary Python libraries, run the following command:

```bash
pip install -r requirements.txt
```
## Usage
```shell
cd youtubeUploader
#### Generate and upload English Videos
python main.py --language en
#### Generate and upload Chinese Videos
python main.py --language zh
```
## Contributing

Contributions to the YouTube Upload Project are welcome. To contribute:

Fork the project.
Create a new branch (git checkout -b feature/your_feature).
Make your changes.
Commit your changes (git commit -am 'Add some feature').
Push to the branch (git push origin feature/your_feature).
Open a pull request.

## Acknowledgements

- Thanks to Google for the YouTube Data API and Facebook for the Graph API.
- Chinese social platform upload referenced codes from https://github.com/aceliuchanghong/bili_douyin_xhs_uploader