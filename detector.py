from deepface import DeepFace
import sys
import cv2

image_path = sys.argv[1]

try:
    img = cv2.imread(image_path)

    if img is None:
        print("Gagal membaca gambar.")
        exit()

    # Deteksi wajah + emosi
    result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=True)
    emotion = result[0]['dominant_emotion']
    print(emotion)

except ValueError:
    # Jika tidak ada wajah terdeteksi
    print("Tidak bisa mendeteksi wajah anda")
except Exception as e:
    print("Gagal mendeteksi mood.")
