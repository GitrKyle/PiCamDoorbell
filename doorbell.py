##################################################
# Raspberry Pi Camera Doorbell Notification Email#
# - Captures Image(s) from HTTP/GET              #
# - Run as service, auto button reset/timeout    #
##################################################


import cv2
import requests
import numpy as np
import time
import os
from gpiozero import Button
from smtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Define the GPIO pin for the doorbell button
DOORBELL_BUTTON_PIN = 2  # GPIO2 (Pin 3 + Ground)
doorbell_button = Button(DOORBELL_BUTTON_PIN)

# Define the MJPEG stream URL                                                                                 
url = "http://192.168.40.54/mjpeg?res=full&x0=0&y0=0&x1=1600&y1=1200&quality=21&doublescan=0"

# SMTP settings for sending email
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'xxxxxxxxx@gmail.com' # Sender Email Address
SENDER_PASSWORD = 'xxxxxxx'  # Your Gmail app-specific password (see below)                                                                       
#SENDER_PASSWORD = os.getenv('EMAIL_APP_PASSWORD')  # Get app password from the environment variable
RECEIVER_EMAIL = 'xxxxxxxxx@gmail.com'

# Directory to temp save the images
image_dir = '/home/pi/doorimages/'

# Create the directory if it doesn't exist
os.makedirs(image_dir, exist_ok=True)

# Function to send email with attachments
def send_email_with_attachments(image_files):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = 'Doorbell Alert: 8 Images Captured'

    for image_file in image_files:
        part = MIMEBase('application', 'octet-stream')
        with open(image_file, 'rb') as file:
            part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(image_file)}')
        msg.attach(part)

    try:
        with SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            print(f"Email sent to {RECEIVER_EMAIL}")
    except Exception as e:
        print(f"Error sending email: {e}")

# Function to handle doorbell press and capture images
def doorbell_pressed():
    print("Doorbell pressed!")
    # Prevent multiple presses within 5 seconds
    if time.time() - doorbell_pressed.last_press_time < 5:
        print("Button pressed too soon, ignoring.")
        return  # Ignore if pressed within the last 5 seconds
    doorbell_pressed.last_press_time = time.time()  # Update last press time

    image_files = []
    response = requests.get(url, stream=True)

    if response.status_code == 200:
        bytes_data = b""
        frame_count = 0

        for chunk in response.iter_content(chunk_size=1024):
            bytes_data += chunk
            a = bytes_data.find(b"\xff\xd8")  # JPEG start
            b = bytes_data.find(b"\xff\xd9")  # JPEG end
            if a != -1 and b != -1:
                jpg_data = bytes_data[a:b + 2]
                bytes_data = bytes_data[b + 2:]
                img = cv2.imdecode(np.frombuffer(jpg_data, dtype=np.uint8), cv2.IMREAD_COLOR)

                if img is not None and frame_count < 8:
                    img_path = os.path.join(image_dir, f'doorbell_frame_{frame_count + 1}.jpg')
                    cv2.imwrite(img_path, img)
                    image_files.append(img_path)
                    print(f"Saved image {img_path}")
                    frame_count += 1
                # Number of images to capture
                if frame_count >= 8:
                    break

        # Send email if images are captured
        if image_files:
            send_email_with_attachments(image_files)
            # Play the MP3 file after sending the email
            os.system('mpg123 /home/pi/doorimages/Doorbell.mp3')
#	     os.system('mpg123 -a default /home/pi/doorimages/Doorbell.mp3')

        else:
            print("No images captured, email not sent.")
    else:
        print("Error: Unable to retrieve the MJPEG stream.")

# Initialize the last press time to a very old value (so first press is always allowed)
doorbell_pressed.last_press_time = 0

# Attach event handler for button press (this resets the listener after each press)
doorbell_button.when_pressed = doorbell_pressed

# Main loop to keep checking button press
try:
    while True:
        time.sleep(0.1)  # The loop will continue to run and listen for the button press
except KeyboardInterrupt:
    print("Program interrupted")
