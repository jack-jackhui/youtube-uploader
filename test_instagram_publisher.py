import unittest
from unittest.mock import Mock, call, patch

import instagram_publisher


TRANSIENT_STATUS = "Error: Media upload has failed with error code 2207085"


def response(status_code, payload):
    mocked = Mock()
    mocked.status_code = status_code
    mocked.json.return_value = payload
    mocked.text = ""
    return mocked


class InstagramPublisherTests(unittest.TestCase):
    @patch("instagram_publisher.time.sleep")
    @patch("instagram_publisher.requests.get")
    @patch("instagram_publisher.requests.post")
    def test_transient_processing_error_recreates_once_and_publishes_once(self, post, get, sleep):
        post.side_effect = [
            response(200, {"id": "container-1"}),
            response(200, {"id": "container-2"}),
            response(200, {"id": "media-1"}),
        ]
        get.side_effect = [
            response(200, {"status_code": "IN_PROGRESS", "status": "Processing"}),
            response(200, {"status_code": "IN_PROGRESS", "status": "Processing"}),
            response(200, {"status_code": "ERROR", "status": TRANSIENT_STATUS}),
            response(200, {"status_code": "FINISHED", "status": "Finished"}),
        ]

        result = instagram_publisher.publish_video_to_instagram(
            "ig-user", "https://example.invalid/video.mp4", "secret-token",
            max_retries=5, retry_wait=3, transient_retry_wait=7,
        )

        self.assertEqual(result, (True, {"media_id": "media-1"}))
        self.assertEqual(
            [request.args[0] for request in post.call_args_list],
            [
                "https://graph.facebook.com/v20.0/ig-user/media",
                "https://graph.facebook.com/v20.0/ig-user/media",
                "https://graph.facebook.com/v20.0/ig-user/media_publish",
            ],
        )
        self.assertEqual(sleep.call_args_list, [call(3), call(3), call(7)])

    @patch("instagram_publisher.time.sleep")
    @patch("instagram_publisher.requests.get")
    @patch("instagram_publisher.requests.post")
    def test_repeated_transient_processing_error_stops_after_one_retry(self, post, get, sleep):
        post.side_effect = [
            response(200, {"id": "container-1"}),
            response(200, {"id": "container-2"}),
        ]
        get.side_effect = [
            response(200, {"status_code": "ERROR", "status": TRANSIENT_STATUS}),
            response(200, {"status_code": "ERROR", "status": TRANSIENT_STATUS}),
        ]

        success, result = instagram_publisher.publish_video_to_instagram(
            "ig-user", "https://example.invalid/video.mp4", "secret-token",
            transient_retry_wait=7,
        )

        self.assertFalse(success)
        self.assertEqual(result["error_code"], 2207085)
        self.assertEqual(result["context"]["processing_code"], 2207085)
        self.assertEqual(result["context"]["container_ids"], ["container-1", "container-2"])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(sleep.call_args_list, [call(7)])

    @patch("instagram_publisher.time.sleep")
    @patch("instagram_publisher.requests.get")
    @patch("instagram_publisher.requests.post")
    def test_non_transient_processing_error_does_not_recreate(self, post, get, sleep):
        post.return_value = response(200, {"id": "container-1"})
        get.return_value = response(200, {
            "status_code": "ERROR",
            "status": "Unsupported video format",
            "access_token": "secret-token",
        })

        success, result = instagram_publisher.publish_video_to_instagram(
            "ig-user", "https://example.invalid/video.mp4", "secret-token",
        )

        self.assertFalse(success)
        self.assertIsNone(result["error_code"])
        self.assertEqual(result["context"]["container_ids"], ["container-1"])
        self.assertEqual(result["context"]["status_payload"]["access_token"], "[REDACTED]")
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()

    @patch("instagram_publisher.requests.get")
    def test_status_get_passes_token_in_params_not_url(self, get):
        get.return_value = response(200, {"status_code": "FINISHED", "status": "Finished"})

        result = instagram_publisher.check_media_container_status("container-1", "secret-token")

        self.assertEqual(result, ("FINISHED", None))
        url = get.call_args.args[0]
        self.assertNotIn("secret-token", url)
        self.assertNotIn("access_token", url)
        self.assertEqual(get.call_args.kwargs["params"]["access_token"], "secret-token")

    @patch("instagram_publisher.time.sleep")
    @patch("instagram_publisher.requests.get")
    @patch("instagram_publisher.requests.post")
    def test_successful_flow_is_unchanged(self, post, get, sleep):
        post.side_effect = [
            response(200, {"id": "container-1"}),
            response(200, {"id": "media-1"}),
        ]
        get.side_effect = [
            response(200, {"status_code": "IN_PROGRESS", "status": "Processing"}),
            response(200, {"status_code": "FINISHED", "status": "Finished"}),
        ]

        result = instagram_publisher.publish_video_to_instagram(
            "ig-user", "https://example.invalid/video.mp4", "secret-token",
            caption="Caption", retry_wait=2,
        )

        self.assertEqual(result, (True, {"media_id": "media-1"}))
        self.assertEqual(post.call_count, 2)
        self.assertTrue(post.call_args_list[-1].args[0].endswith("/media_publish"))
        sleep.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
