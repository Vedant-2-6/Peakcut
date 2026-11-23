"""Tests for post-upload clip deletion lifecycle and automated SEO enqueueing."""
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import accounts, config, ctx, jobs, posting, seo


class TestPostingLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pk_lifecycle_test_"))
        self.uid = "test_user_lifecycle"

        self._orig_data_dir = config.DATA_DIR
        self._orig_users_dir = config.USERS_DIR
        config.DATA_DIR = self.tmp / "data"
        config.USERS_DIR = self.tmp / "users"
        (self.tmp / "data").mkdir(parents=True, exist_ok=True)
        (self.tmp / "users" / self.uid).mkdir(parents=True, exist_ok=True)

        self._orig_uid = ctx.uid
        ctx.uid = lambda: self.uid

        self._orig_posts = posting._posts
        posting._posts = []
        self._orig_file = posting._FILE
        posting._FILE = self.tmp / "data" / "posts.json"

    def tearDown(self):
        config.DATA_DIR = self._orig_data_dir
        config.USERS_DIR = self._orig_users_dir
        ctx.uid = self._orig_uid
        posting._posts = self._orig_posts
        posting._FILE = self._orig_file
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_on_clip_ready_auto_seo_and_enqueue(self):
        job_dir = self.tmp / "jobs" / "job_seo_1"
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        clip_file = clips_dir / "clip1.mp4"
        clip_file.write_bytes(b"dummy mp4 content")
        cover_file = clips_dir / "clip1.jpg"
        cover_file.write_bytes(b"dummy jpg content")

        job = {
            "id": "job_seo_1",
            "user": self.uid,
            "dir": str(job_dir),
            "creator": "creator_gta",
            "uploader": "IShowSpeed",
            "game": "GTA 6",
            "clips": [{
                "id": "clip1",
                "file": "clip1.mp4",
                "cover": "clip1.jpg",
                "hook": "Speed found the secret submarine",
                "status": "done",
                "version": 1,
                "score": 92
            }]
        }

        yt_acc = {"id": "acc_yt_1", "platform": "youtube", "name": "Speed Clips", "added": time.time(), "detail": ""}
        orig_list_accounts = accounts.list_accounts
        orig_get_account = accounts.get
        orig_get_job = jobs.get
        orig_save_job = jobs.save

        try:
            accounts.list_accounts = lambda: [yt_acc]
            accounts.get = lambda aid: yt_acc if aid == "acc_yt_1" else None
            jobs.get = lambda jid: job if jid == "job_seo_1" else None
            jobs.save = lambda j: None

            clip = job["clips"][0]
            posting.on_clip_ready(job, clip)

            # 1. Verify SEO metadata enriched
            self.assertTrue("#Shorts" in clip["title"] or "GTA 6" in clip["title"])
            self.assertTrue(len(clip["hashtags"]) > 0)
            self.assertTrue("GTA 6" in clip["description"])

            # 2. Verify auto-enqueued for YouTube without waiting for confirmation
            posts = posting._posts
            self.assertEqual(len(posts), 1)
            p = posts[0]
            self.assertEqual(p["job"], "job_seo_1")
            self.assertEqual(p["clip"], "clip1")
            self.assertEqual(p["platform"], "youtube")
            self.assertEqual(p["status"], "scheduled")
            self.assertLessEqual(p["due_at"], time.time() + 2)
        finally:
            accounts.list_accounts = orig_list_accounts
            accounts.get = orig_get_account
            jobs.get = orig_get_job
            jobs.save = orig_save_job

    def test_single_platform_lifecycle_immediate_deletion(self):
        job_dir = self.tmp / "jobs" / "job_single"
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        clip_file = clips_dir / "c_single.mp4"
        clip_file.write_bytes(b"video bytes")
        cover_file = clips_dir / "c_single.jpg"
        cover_file.write_bytes(b"cover bytes")

        job = {
            "id": "job_single",
            "user": self.uid,
            "dir": str(job_dir),
            "creator": "c1",
            "clips": [{
                "id": "c_single",
                "file": "c_single.mp4",
                "cover": "c_single.jpg",
                "status": "done",
                "version": 1
            }]
        }

        yt_acc = {"id": "yt_1", "platform": "youtube", "name": "YT Channel"}
        orig_get_acc = accounts.get
        orig_yt_upload = accounts.youtube_upload
        orig_get_job = jobs.get
        orig_save_job = jobs.save

        try:
            accounts.get = lambda aid: yt_acc if aid == "yt_1" else None
            accounts.youtube_upload = lambda *args, **kwargs: ("yt_123", "https://youtube.com/shorts/yt_123")
            jobs.get = lambda jid: job if jid == "job_single" else None
            jobs.save = lambda j: None

            p = {
                "id": "post_yt_1",
                "user": self.uid,
                "job": "job_single",
                "clip": "c_single",
                "creator": "c1",
                "account": "yt_1",
                "account_name": "YT Channel",
                "platform": "youtube",
                "status": "scheduled",
                "due_at": time.time(),
                "tries": 0
            }
            posting._posts = [p]

            self.assertTrue(clip_file.exists())
            self.assertTrue(cover_file.exists())

            # Execute post
            posting._post(p)

            # Post should succeed
            self.assertEqual(p["status"], "posted")
            self.assertEqual(p["url"], "https://youtube.com/shorts/yt_123")

            # Local .mp4 file must be deleted immediately
            self.assertFalse(clip_file.exists())
            # Cover thumbnail must be kept for UI
            self.assertTrue(cover_file.exists())
            # Clip marked as purged
            self.assertTrue(job["clips"][0].get("purged"))
        finally:
            accounts.get = orig_get_acc
            accounts.youtube_upload = orig_yt_upload
            jobs.get = orig_get_job
            jobs.save = orig_save_job

    def test_multi_platform_lifecycle_delayed_deletion(self):
        job_dir = self.tmp / "jobs" / "job_multi"
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        clip_file = clips_dir / "c_multi.mp4"
        clip_file.write_bytes(b"video bytes multi")
        cover_file = clips_dir / "c_multi.jpg"
        cover_file.write_bytes(b"cover bytes multi")

        job = {
            "id": "job_multi",
            "user": self.uid,
            "dir": str(job_dir),
            "creator": "c1",
            "clips": [{
                "id": "c_multi",
                "file": "c_multi.mp4",
                "cover": "c_multi.jpg",
                "status": "done",
                "version": 1
            }]
        }

        yt_acc = {"id": "yt_acc", "platform": "youtube", "name": "YT"}
        ig_acc = {"id": "ig_acc", "platform": "instagram", "name": "IG"}

        orig_get_acc = accounts.get
        orig_yt_upload = accounts.youtube_upload
        orig_ig_upload = accounts.instagram_upload
        orig_get_job = jobs.get
        orig_save_job = jobs.save

        try:
            accounts.get = lambda aid: yt_acc if aid == "yt_acc" else ig_acc if aid == "ig_acc" else None
            accounts.youtube_upload = lambda *args, **kwargs: ("yt_999", "https://youtube.com/shorts/yt_999")
            accounts.instagram_upload = lambda *args, **kwargs: ("ig_888", "https://instagram.com/reel/ig_888")
            jobs.get = lambda jid: job if jid == "job_multi" else None
            jobs.save = lambda j: None

            p_yt = {
                "id": "p_yt",
                "user": self.uid,
                "job": "job_multi",
                "clip": "c_multi",
                "creator": "c1",
                "account": "yt_acc",
                "account_name": "YT",
                "platform": "youtube",
                "status": "scheduled",
                "due_at": time.time(),
                "tries": 0
            }
            p_ig = {
                "id": "p_ig",
                "user": self.uid,
                "job": "job_multi",
                "clip": "c_multi",
                "creator": "c1",
                "account": "ig_acc",
                "account_name": "IG",
                "platform": "instagram",
                "status": "scheduled",
                "due_at": time.time() + 100,
                "tries": 0
            }
            posting._posts = [p_yt, p_ig]

            # 1. Post to YouTube first
            posting._post(p_yt)
            self.assertEqual(p_yt["status"], "posted")

            # Because Instagram post is still scheduled, local file MUST NOT be deleted yet!
            self.assertTrue(clip_file.exists())
            self.assertFalse(bool(job["clips"][0].get("purged")))

            # 2. Now post to Instagram
            posting._post(p_ig)
            self.assertEqual(p_ig["status"], "posted")

            # Both platforms are posted -> Local .mp4 file MUST be deleted now!
            self.assertFalse(clip_file.exists())
            self.assertTrue(cover_file.exists())
            self.assertTrue(job["clips"][0].get("purged"))
        finally:
            accounts.get = orig_get_acc
            accounts.youtube_upload = orig_yt_upload
            accounts.instagram_upload = orig_ig_upload
            jobs.get = orig_get_job
            jobs.save = orig_save_job


if __name__ == "__main__":
    unittest.main()
