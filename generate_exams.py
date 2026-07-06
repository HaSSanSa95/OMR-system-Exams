import json
import os
import uuid
from PIL import Image, ImageDraw, ImageFont
import qrcode 
import arabic_reshaper
from bidi.algorithm import get_display

FONT_PATH = 'NotoKufiArabic-Regular.ttf' 
WIDTH, HEIGHT = 1240, 1754 
MARGIN = 70 
OPTION_LETTERS = ['A', 'B', 'C', 'D']

def fix_arabic_text(text):
    if not text: return ""
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def get_text_metrics(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def wrap_text(text, font, max_width, draw):
    words = text.split(' ')
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        w, _ = get_text_metrics(draw, test_line, font)
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line: lines.append(' '.join(current_line))
            current_line = [word]
    if current_line: lines.append(' '.join(current_line))
    return lines

def generate_qrcode(data_dict, path):
    """
    توليد الـ QR Code بالـ JSON المطلوب تماماً.
    """
    qr_content = json.dumps(data_dict, ensure_ascii=False)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=2)
    qr.add_data(qr_content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(path)

def draw_header(img, draw, exam_info, user_data, qr_p, f_l, f_m, cursor_y):
    marker_size = 40
    draw.rectangle([MARGIN, MARGIN, MARGIN+marker_size, MARGIN+marker_size], fill='white')
    draw.rectangle([WIDTH-MARGIN-marker_size, MARGIN, WIDTH-MARGIN, MARGIN+marker_size], fill='white')
    draw.rectangle([MARGIN, HEIGHT-MARGIN-marker_size, MARGIN+marker_size, HEIGHT-MARGIN], fill='white')
    draw.rectangle([WIDTH-MARGIN-marker_size, HEIGHT-MARGIN-marker_size, WIDTH-MARGIN, HEIGHT-MARGIN], fill='white')

    if qr_p and os.path.exists(qr_p):
        qr_i = Image.open(qr_p).convert("RGBA").resize((150, 150))
        img.paste(qr_i, (MARGIN + 50, MARGIN + 10), qr_i)
        
    h_txt = fix_arabic_text(f"امتحان: {exam_info.get('subject_name')} - {exam_info.get('stage')}")
    tw, th = get_text_metrics(draw, h_txt, f_l)
    draw.text(((WIDTH - tw) / 2, cursor_y + 20), h_txt, fill='black', font=f_l)
    
    cursor_y += th + 40
    details = [f"الطالب: {user_data.get('name')}", f"الرقم: {user_data.get('id')}", f"النموذج: {user_data.get('model_type')}"]
    for det in details:
        proc = fix_arabic_text(det)
        tw, th = get_text_metrics(draw, proc, f_m)
        draw.text((WIDTH - MARGIN - 50 - tw, cursor_y), proc, fill='black', font=f_m)
        cursor_y += th + 12
    return cursor_y + 30

def create_exam_pages(exam_info, user_data, f_l, f_m, f_s):
    pages = []
    questions = user_data.get('exam', [])
    img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
    draw = ImageDraw.Draw(img)
    cursor_y = draw_header(img, draw, exam_info, user_data, None, f_l, f_m, MARGIN)
    available_width = WIDTH - 2 * MARGIN - 20
    
    RLM = "\u200f"

    for idx, q_item in enumerate(questions, 1):
        q_obj = q_item.get('question', q_item)
        full_q_text = f"{idx}. {q_obj.get('question_text', {}).get('text', '')}"
        wrapped_q = wrap_text(full_q_text, f_s, available_width, draw)
        
        for line in wrapped_q:
            if cursor_y + 60 > HEIGHT - MARGIN:
                pages.append(img)
                img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
                draw = ImageDraw.Draw(img)
                cursor_y = draw_header(img, draw, exam_info, user_data, None, f_l, f_m, MARGIN)
            proc_q = fix_arabic_text(line)
            tw, th = get_text_metrics(draw, proc_q, f_s)
            draw.text((WIDTH - MARGIN - tw, cursor_y), proc_q, fill='black', font=f_s)
            cursor_y += th + 15
            
        opts = q_obj.get('options', [])[:4]
        for i, opt in enumerate(opts):
            letter = OPTION_LETTERS[i]
            full_opt_text = f"{RLM}({letter}) {opt.get('text', '')}"  
            wrapped_opt = wrap_text(full_opt_text, f_s, available_width - 80, draw)
            for o_line in wrapped_opt:
                if cursor_y + 40 > HEIGHT - MARGIN:
                    pages.append(img)
                    img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
                    draw = ImageDraw.Draw(img)
                    cursor_y = draw_header(img, draw, exam_info, user_data, None, f_l, f_m, MARGIN)
                
                proc_o = fix_arabic_text(o_line)
                tw_o, th_o = get_text_metrics(draw, proc_o, f_s)
                
                draw.text((WIDTH - MARGIN - 80 - tw_o, cursor_y), proc_o, fill='black', font=f_s)
                cursor_y += th_o + 12
        
        cursor_y += 20
        draw.line([(MARGIN, cursor_y), (WIDTH - MARGIN, cursor_y)], fill='#DDDDDD', width=1)
        cursor_y += 30
        
    pages.append(img)
    return pages


def create_bubble_sheet_and_map(info, user, qr_path, font_l, font_m, font_s):
    # 1. إنشاء خلفية بيضاء بحجم A4 قياسي
    img = Image.new('RGB', (1240, 1754), 'white')
    draw = ImageDraw.Draw(img)
    master_coords = []
    
    # 2. رسم علامات المحاذاة السوداء الأربعة في الأركان للكاميرا
    marks = [(50, 50), (1150, 50), (50, 1664), (1150, 1664)]
    for x, y in marks:
        draw.rectangle([x, y, x+40, y+40], fill="black")
        
    # 3. عنوان الورقة الرئيسي
    title = fix_arabic_text("ورقة إجابة امتحانية (Bubble Sheet)")
    tw, th = get_text_metrics(draw, title, font_l)
    draw.text((620 - int(tw) // 2, 70), title, fill="black", font=font_l)
    
    # 4. رسم حقل معلومات الطالب اليمين
    draw.rectangle([620, 140, 1150, 465], outline="black", width=2)
    
    info_title = fix_arabic_text("معلومات الطالب والامتحان:")
    tw, th = get_text_metrics(draw, info_title, font_m)
    draw.text((1120 - int(tw), 160), info_title, fill="black", font=font_m)
    
    labels = [
        f"اسم الطالب: {user.get('name', 'غير محدد')}",
        f"المادة الدراسية: {info.get('subject_name', 'غير محدد')}",
        f"المرحلة / الصف: {info.get('stage', 'غير محدد')}",
        f"نموذج الأسئلة: {user.get('model_type', 'A')}"
    ]
    
    start_txt_y = 210
    for label in labels:
        txt = fix_arabic_text(label)
        tw, th = get_text_metrics(draw, txt, font_m)
        draw.text((1120 - int(tw), start_txt_y), txt, fill="black", font=font_m)
        draw.line([640, start_txt_y + 35, 1120, start_txt_y + 35], fill="lightgray", width=1)
        start_txt_y += 55

    # 5. [تعديل جوهري] استبدال دوائر الرقم الامتحاني بـ الـ QR Code مباشرة
    draw.rectangle([90, 140, 580, 465], outline="black", width=2)
    
    id_title = fix_arabic_text("بيانات التحقق الذكي (QR Code)")
    tw, th = get_text_metrics(draw, id_title, font_m)
    draw.text((335 - int(tw) // 2, 155), id_title, fill="black", font=font_m)
    
    # تحميل ولصق صورة الـ QR Code الخاصة بالطالب داخل هذا المربع
    if qr_path and os.path.exists(qr_path):
        # حجم مناسب يتلاءم تماماً مع أبعاد المربع (240x240 بكسل)
        qr_img = Image.open(qr_path).convert("RGB").resize((240, 240))
        # الحساب ليكون متمركزاً في وسط المربع تماماً
        img.paste(qr_img, (335 - 120, 210))

    # 6. رسم أعمدة الأسئلة الـ 100 
    start_y = 500 
    col_width = 265     
    row_height = 45     
    q_bubble_radius = 14 
    
    options = ['A', 'B', 'C', 'D']
    
    for i in range(100):
        col = i // 25
        row = i % 25
        
        q_x = 90 + (col * col_width)
        q_y = start_y + (row * row_height)
        
        q_num = fix_arabic_text(f"{i + 1}-")
        draw.text((q_x + 5, q_y + 5), q_num, fill="black", font=font_m)
        
        bubble_start_x = q_x + 55
        for j, opt in enumerate(options):
            bx = bubble_start_x + (j * 50)
            by = q_y
            
            draw.ellipse([bx, by, bx + q_bubble_radius*2, by + q_bubble_radius*2], outline="black", width=1)
            draw.text((bx + q_bubble_radius, by + q_bubble_radius), opt, fill="black", font=font_s, anchor="mm")
            
            master_coords.append({
                "q": i + 1,
                "opt": opt,
                "bbox": [bx, by, bx + q_bubble_radius*2, by + q_bubble_radius*2]
            })
            
    return [img], master_coords

def generate_all(target_dir='exam_sheets_pdf_output', Jsonpath=None):
    if not os.path.exists(target_dir): os.makedirs(target_dir)
    
    json_to_read = Jsonpath if (Jsonpath and os.path.exists(Jsonpath)) else 'new_json.json'
    
    try:
        with open(json_to_read, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
            data = full_data.get('data', [full_data])[0]
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return None
    
    info = {'stage': data.get('stage'), 'subject_name': data.get('subject')}
    master_coords, all_final_pages, temp_qrs = [], [], []
    
    f_l = ImageFont.truetype(FONT_PATH, 28)
    f_m = ImageFont.truetype(FONT_PATH, 22)
    f_s = ImageFont.truetype(FONT_PATH, 18)
    f_xs = ImageFont.truetype(FONT_PATH, 16)
    
    # جلب الـ id الخاص بالامتحان (exam_id) من حقل الـ JSON الرئيسي
    levelID = int(data.get('id', 681))
    
    for user in data.get('users', []):
        # جلب الـ user_id الخاص بالطالب وتحويله لـ int ليتوافق مع الـ API
        u_id = int(user.get('id', user.get('user_id', 59)))
        u_model = data.get('exam_info', {}).get('model_type', 'A')
        
        user_p = {
            'id': u_id, 
            'name': user.get('user_name', user.get('name', 'N/A')), 
            'model_type': u_model, 
            'exam': [(q if 'question' in q else {'question': q}) for q in user.get('exam', [])]
        }
        
        # إنشاء مسار مؤقت لصورة الـ QR
        qr_p = os.path.join(target_dir, f"qr_{u_id}_{uuid.uuid4().hex[:6]}.png")
        
        # 🛑 [تعديل] صياغة مصفوفة الـ data_exams المطلوبة تماماً داخل الـ QR Code
        qr_payload = {
            "data_exams": [
                {
                    "id": levelID,
                    "user_id": u_id
                }
            ]
        }
        
        generate_qrcode(qr_payload, qr_p)
        temp_qrs.append(qr_p)
        
        # تمرير مسار الـ QR الصادر ليتم لصقه بالورقة
        bubble_pages, current_coords = create_bubble_sheet_and_map(info, user_p, qr_p, f_l, f_m, f_xs)
        all_final_pages.extend(bubble_pages) 
        
        exam_pages = create_exam_pages(info, user_p, f_l, f_m, f_s)
        all_final_pages.extend(exam_pages)
        
        if len(current_coords) > len(master_coords):
            master_coords = current_coords
            
    if all_final_pages:
        pdf_path = os.path.join(target_dir, "All_Students_Exams.pdf")
        all_final_pages[0].save(pdf_path, save_all=True, append_images=all_final_pages[1:], resolution=150.0)
        
        with open(os.path.join(target_dir, "unified_master_map.json"), 'w', encoding='utf-8') as f:
            json.dump(master_coords, f, ensure_ascii=False, indent=4)

        # تنظيف الصور المؤقتة للـ QR بعد حزمها بالـ PDF المشترك
        for qp in temp_qrs:
            if os.path.exists(qp): os.remove(qp)
            
        return {"pdf_path": pdf_path, "json_path": "unified_master_map.json"}
    
    return None

if __name__ == '__main__':
    generate_all()