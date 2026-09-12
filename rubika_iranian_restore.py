"""Keep the Iranian Rubika menu active after generic runtime patches."""
import os

CONTACT_USERNAME = os.getenv("CONTACT_USERNAME", "Good_ok_2000").strip().lstrip("@") or "Good_ok_2000"


def install():
    import server
    import rubika_v2 as rb
    import rubika_iranian_complaints as iran

    iran.install(rb)
    original_patch = server._patch_rubika
    if getattr(server, "_netyar_iranian_restore_patch", False):
        iran.restore(rb)
        return

    def patched(rubika):
        original_patch(rubika)
        if getattr(rubika, "_iranian_complaints_installed", False):
            iran.restore(rubika)

    server._patch_rubika = patched
    server._netyar_iranian_restore_patch = True
    iran.restore(rb)
