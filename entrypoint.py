"""Production entrypoint shared by Railway and local execution."""

from runtime_patches import install

server = install()


if __name__ == "__main__":
    server.main()
