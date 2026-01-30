from helpers.notifications import Notifier

def main():
    notifier = Notifier()

    notifier.send(
        report="DUK008",
        status="TEST",
        message="This is a test notification from Python"
    )

    print("Notification sent")

if __name__ == "__main__":
    main()
