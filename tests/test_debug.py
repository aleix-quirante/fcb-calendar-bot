import sys


def test_debug():
    print("sys.path:", sys.path)
    try:
        import src.calendar_cleaner.cleaner

        print("Import succeeded")
    except ImportError as e:
        print("Import failed:", e)
    assert True
