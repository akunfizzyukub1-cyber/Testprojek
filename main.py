class VideoGenerator:
    async def generate(self, topic, mode, style):
        return {
            "metadata": {
                "title": f"{topic}"
            },
            "video_path": __import__("pathlib").Path("dummy.mp4")
        }


class Logger:
    @staticmethod
    def error(msg):
        print("[ERROR]", msg)
