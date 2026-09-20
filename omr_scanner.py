import cv2
import numpy as np
import json
import os


def decode_qr(image):
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(image)
    return data if data else None

def get_filled_ratio(roi):
    if roi.size == 0: return 0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 4)
    return cv2.countNonZero(thresh) / float(roi.shape[0] * roi.shape[1])

def debug_omr_coords(image_path, json_path, output_debug_path="debug_result.jpg"):
    img = cv2.imread(image_path)
    if img is None: return
    
    img_resized = cv2.resize(img, (1240, 1754))
    with open(json_path, 'r', encoding='utf-8') as f:
        master_coords = json.load(f)
        
    for entry in master_coords:
        x1, y1, x2, y2 = entry['bbox']
        cv2.rectangle(img_resized, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{entry['q']}{entry['opt']}"
        cv2.putText(img_resized, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

    cv2.imwrite(output_debug_path, img_resized)

def find_actual_bubble_and_rate(img, x1, y1, x2, y2):
    p = 15 
    roi = img[max(0, y1-p):min(img.shape[0], y2+p), max(0, x1-p):min(img.shape[1], x2+p)]
    if roi.size == 0: return 0, (x1, y1, x2, y2)
    
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=50, param2=18, minRadius=10, maxRadius=22)
    
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        best_r, best_c = 0, (x1, y1, x2, y2)
        for (cx, cy, cr) in circles:
            b_roi = roi[max(0, cy-cr):cy+cr, max(0, cx-cr):cx+cr]
            r = get_filled_ratio(b_roi)
            if r > best_r:
                best_r = r
                best_c = (max(0, x1-p)+cx-cr, max(0, y1-p)+cy-cr, max(0, x1-p)+cx+cr, max(0, y1-p)+cy+cr)
        return best_r, best_c
    
    return get_filled_ratio(img[y1:y2, x1:x2]), (x1, y1, x2, y2)


def process_omr_smart(image_path, json_path, sensitivity=12):
    """
    معالجة ورقة الإجابة لاستخراج الإجابات، رقم الطالب، ونموذج الأسئلة بناءً على ملف الـ JSON.
    """

    image = cv2.imread(image_path)
    if image is None:
        return {"status": "error", "message": "Could not open or find the image"}

    img_resized = cv2.resize(image, (1240, 1754))
    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    output_image = img_resized.copy()

    if not os.path.exists(json_path):
        return {"status": "error", "message": f"JSON path not found: {json_path}"}
        
    with open(json_path, 'r', encoding='utf-8') as f:
        master_coords = json.load(f)

    coords_by_question = {}    
    coords_by_student_id = {}  
    coords_by_model = {}       

    for entry in master_coords:
        key = str(entry['q'])
        opt = str(entry['opt'])
        bbox = entry['bbox']
        
   
        if "student" in key.lower() or "id" in key.lower():
            if key not in coords_by_student_id:
                coords_by_student_id[key] = {}
            coords_by_student_id[key][opt] = bbox
        elif "model" in key.lower() or "form" in key.lower() or "randum" in key.lower():
            if key not in coords_by_model:
                coords_by_model[key] = {}
            coords_by_model[key][opt] = bbox
        else:
           
            if key not in coords_by_question:
                coords_by_question[key] = {}
            coords_by_question[key][opt] = bbox

    student_id_digits = {}
    for field_name in sorted(coords_by_student_id.keys()):
        option_means = {}
        for digit_val, bbox in coords_by_student_id[field_name].items():
            x1, y1, x2, y2 = bbox
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(1240, x2), min(1754, y2)
            if (x2 - x1) <= 0 or (y2 - y1) <= 0: continue
            
            roi = gray[y1:y2, x1:x2]
            option_means[digit_val] = cv2.mean(roi)[0]
            cv2.rectangle(output_image, (x1, y1), (x2, y2), (255, 0, 0), 2) # رسم مربع أزرق لهوية الطالب

        if option_means:
            darkest_digit = min(option_means, key=option_means.get)
            darkest_value = option_means[darkest_digit]
            other_values = [v for k, v in option_means.items() if k != darkest_digit]
            average_of_others = sum(other_values) / len(other_values) if other_values else 255
            
            if (average_of_others - darkest_value) > sensitivity:
                student_id_digits[field_name] = darkest_digit
                x1_t, y1_t, _, _ = coords_by_student_id[field_name][darkest_digit]
                cv2.putText(output_image, darkest_digit, (x1_t, y1_t - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    detected_student_id = "".join([student_id_digits[k] for k in sorted(student_id_digits.keys())])
    if not detected_student_id:
       
        qr_val = decode_qr(img_resized)
        detected_student_id = qr_val if qr_val else "null"

    detected_model = "null"
    for field_name in coords_by_model.keys():
        option_means = {}
        for model_type, bbox in coords_by_model[field_name].items():
            x1, y1, x2, y2 = bbox
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(1240, x2), min(1754, y2)
            if (x2 - x1) <= 0 or (y2 - y1) <= 0: continue
            
            roi = gray[y1:y2, x1:x2]
            option_means[model_type] = cv2.mean(roi)[0]
            cv2.rectangle(output_image, (x1, y1), (x2, y2), (0, 165, 255), 2) # مربع برتقالي للنموذج

        if option_means:
            darkest_model = min(option_means, key=option_means.get)
            darkest_value = option_means[darkest_model]
            other_values = [v for k, v in option_means.items() if k != darkest_model]
            average_of_others = sum(other_values) / len(other_values) if other_values else 255
            
            if (average_of_others - darkest_value) > sensitivity:
                detected_model = darkest_model
                x1_t, y1_t, _, _ = coords_by_model[field_name][darkest_model]
                cv2.putText(output_image, darkest_model, (x1_t, y1_t - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

    answers = {}
    for question_num in range(1, 101):
        q_str = str(question_num)
        options = ["أ", "ب", "ج", "د"]
        option_means = {}

        if q_str not in coords_by_question:
            answers[q_str] = "null"
            continue

        for option_letter in options:
            if option_letter not in coords_by_question[q_str]:
                continue
            
            x1, y1, x2, y2 = coords_by_question[q_str][option_letter]
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(1240, x2), min(1754, y2)
            if (x2 - x1) <= 0 or (y2 - y1) <= 0: continue

            roi = gray[y1:y2, x1:x2]
            option_means[option_letter] = cv2.mean(roi)[0]
            cv2.rectangle(output_image, (x1, y1), (x2, y2), (0, 255, 0), 2) # مربع أخضر للإجابات

        selected_option = "null"
        if option_means:
            darkest_option = min(option_means, key=option_means.get)
            darkest_value = option_means[darkest_option]
            other_values = [v for k, v in option_means.items() if k != darkest_option]
            average_of_others = sum(other_values) / len(other_values) if other_values else 255
            
            if (average_of_others - darkest_value) > sensitivity:
                selected_option = darkest_option
                x1_text, y1_text, _, _ = coords_by_question[q_str][selected_option]
                cv2.putText(output_image, selected_option, (x1_text, y1_text - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        answers[q_str] = selected_option
    cv2.imwrite("processed_sheet.png", output_image)
    return {
        "status": "processed",
        "student_id": detected_student_id,
        "exam_model": detected_model,
        "answers": answers,
        "processed_image_path": "processed_sheet.png"
    }

if __name__ == "__main__":
    image_file = "TestPage.jpg"
    json_file = "master_coordinates.json" 
    
    if os.path.exists(image_file) and os.path.exists(json_file):
        result = process_omr_smart(image_file, json_file, sensitivity=10)
        print("\n--- النتيجة الشاملة والنهائية ---")
        print(f"رقم الطالب المكتشف: {result['student_id']}")
        print(f"نموذج الأسئلة المكتشف: {result['exam_model']}")
        print(f"عدد الأسئلة المقروءة: {len(result['answers'])}")
    else:
        print("الرجاء التأكد من صحة مسار ملف الصورة وملف الـ JSON لتشغيل الاختبار بنجاح.")