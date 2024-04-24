import youtube_manager

def test_youtube_upload():
    youtube = youtube_manager.authenticate_youtube()
    video_file = 'downloaded_videos/final-1.mp4'  # Path to your test video file
    video_title = "Test Video Title"
    video_description = "This is a test description for the video upload."
    video_tags = ["test", "video", "upload"]  # Example tags

    print("Uploading test video to YouTube...")
    upload_response = youtube_manager.upload_video(youtube, video_file, video_title, video_description, video_tags)

    if upload_response:
        print("Test video uploaded successfully. Video ID:", upload_response['id'])
    else:
        print("Failed to upload test video.")
