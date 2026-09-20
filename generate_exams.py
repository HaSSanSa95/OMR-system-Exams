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
OPTION_LETTERS = ['أ', 'ب', 'ج', 'د']

def to_hindi_digits(number):
    arabic_digits = "0123456789"
    hindi_digits = "٠١٢٣٤٥٦٧٨٩"
    trans_table = str.maketrans(arabic_digits, hindi_digits)
    return str(number).translate(trans_table)

def load_font(font_path, size):
    try:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

def fix_arabic_text(text):
    if not text: 
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

def get_text_metrics(draw, text, font):
    if not text:
        return 0, 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(0, bbox[2] - bbox[0]), max(0, bbox[3] - bbox[1])

def wrap_text(text, font, max_width, draw):
    if not text:
        return []
    words = [w for w in text.split(' ') if w]
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        proc_test = fix_arabic_text(test_line)
        w, _ = get_text_metrics(draw, proc_test, font)
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line: 
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line: 
        lines.append(' '.join(current_line))
    return lines

def generate_qrcode(data_dict, path):
    qr_content = json.dumps(data_dict, ensure_ascii=False)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=2)
    qr.add_data(qr_content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(path)

def draw_header(img, draw, exam_info, user_data, qr_p, f_l, f_m, cursor_y):
    marker_size = 40
    draw.rectangle([MARGIN, MARGIN, MARGIN + marker_size, MARGIN + marker_size], fill='black')
    draw.rectangle([WIDTH - MARGIN - marker_size, MARGIN, WIDTH - MARGIN, MARGIN + marker_size], fill='black')
    draw.rectangle([MARGIN, HEIGHT - MARGIN - marker_size, MARGIN + marker_size, HEIGHT - MARGIN], fill='black')
    draw.rectangle([WIDTH - MARGIN - marker_size, HEIGHT - MARGIN - marker_size, WIDTH - MARGIN, HEIGHT - MARGIN], fill='black')

    if qr_p and os.path.exists(qr_p):
        qr_i = Image.open(qr_p).convert("RGBA").resize((130, 130))
        img.paste(qr_i, (MARGIN + 20, MARGIN + 10), qr_i)
        
    h_txt = fix_arabic_text(f"امتحان: {exam_info.get('subject_name', '')} - {exam_info.get('stage', '')}")
    tw, th = get_text_metrics(draw, h_txt, f_l)
    draw.text(((WIDTH - tw) / 2, cursor_y + 10), h_txt, fill='black', font=f_l)
    
    cursor_y += th + 30
    details = [
        f"الطالب: {user_data.get('name', '')}", 
        f"الرقم الامتحاني: {user_data.get('id', '')}", 
        f"نموذج الأسئلة: {user_data.get('model_type', 'A')}"
    ]
    for det in details:
        proc = fix_arabic_text(det)
        tw, th = get_text_metrics(draw, proc, f_m)
        draw.text((WIDTH - MARGIN - 30 - tw, cursor_y), proc, fill='#222222', font=f_m)
        cursor_y += th + 10

    cursor_y += 15
    draw.line([(MARGIN, cursor_y), (WIDTH - MARGIN, cursor_y)], fill='#000000', width=2)
    return cursor_y + 25

def create_exam_pages(exam_info, user_data, f_l, f_m, f_s):
    pages = []
    questions = user_data.get('exam', [])
    img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
    draw = ImageDraw.Draw(img)
    cursor_y = draw_header(img, draw, exam_info, user_data, None, f_l, f_m, MARGIN)
    
    content_right = WIDTH - MARGIN
    available_width = WIDTH - (2 * MARGIN) - 20

    for idx, q_item in enumerate(questions, 1):
        q_obj = q_item.get('question', q_item)
        raw_q_text = q_obj.get('question_text', {}).get('text', '') if isinstance(q_obj.get('question_text'), dict) else str(q_obj.get('question_text', ''))
        
        hindi_idx = to_hindi_digits(idx)
        full_q_text = f"س{hindi_idx}: {raw_q_text}"
        wrapped_q = wrap_text(full_q_text, f_s, available_width, draw)
        
        if cursor_y + (len(wrapped_q) * 30) + 160 > HEIGHT - MARGIN:
            pages.append(img)
            img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
            draw = ImageDraw.Draw(img)
            cursor_y = draw_header(img, draw, exam_info, user_data, None, f_l, f_m, MARGIN)

        for line in wrapped_q:
            proc_q = fix_arabic_text(line)
            tw, th = get_text_metrics(draw, proc_q, f_s)
            draw.text((content_right - tw, cursor_y), proc_q, fill='#111111', font=f_s)
            cursor_y += th + 10
            
        cursor_y += 8
        opts = q_obj.get('options', [])[:4]
        
        opt_indent = 40
        opt_available_width = available_width - opt_indent
        
        for i, opt in enumerate(opts):
            letter = OPTION_LETTERS[i] if i < len(OPTION_LETTERS) else f"{i+1}"
            opt_text = opt.get('text', '') if isinstance(opt, dict) else str(opt)
            full_opt_text = f"({letter})  {opt_text}"
            
            wrapped_opt = wrap_text(full_opt_text, f_s, opt_available_width, draw)
            for o_line in wrapped_opt:
                if cursor_y + 35 > HEIGHT - MARGIN:
                    pages.append(img)
                    img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
                    draw = ImageDraw.Draw(img)
                    cursor_y = draw_header(img, draw, exam_info, user_data, None, f_l, f_m, MARGIN)
                
                proc_o = fix_arabic_text(o_line)
                tw_o, th_o = get_text_metrics(draw, proc_o, f_s)
                draw.text((content_right - opt_indent - tw_o, cursor_y), proc_o, fill='#333333', font=f_s)
                cursor_y += th_o + 8
        
        cursor_y += 12
        draw.line([(MARGIN + 40, cursor_y), (WIDTH - MARGIN - 40, cursor_y)], fill='#E0E0E0', width=1)
        cursor_y += 20

    pages.append(img)
    return pages

def create_bubble_sheet_and_map(info, user, qr_path, font_l, font_m, font_s, logo_path=None):
    img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
    draw = ImageDraw.Draw(img)
    master_coords = []
    
    marks = [(50, 50), (1150, 50), (50, 1664), (1150, 1664)]
    for x, y in marks:
        draw.rectangle([x, y, x + 40, y + 40], fill="black")
        
    # رسم الشعار
    #if logo_path and os.path.exists(logo_path):
       # try:
           # logo_img = Image.open(logo_path).convert("RGBA")
           # logo_img.thumbnail((120, 120)) 
           # img.paste(logo_img, (MARGIN + 20, MARGIN + 10), logo_img)
       # except Exception as e:
         #   print(f"لم يتمكن من رسم الشعار: {e}")

    title = fix_arabic_text("ورقة الإجابة الامتحانية (Bubble Sheet)")
    tw, th = get_text_metrics(draw, title, font_l)
    draw.text((620 - int(tw) // 2, 60), title, fill="black", font=font_l)
    
    draw.rectangle([620, 130, 1150, 450], outline="black", width=2)
    info_title = fix_arabic_text("معلومات الطالب والامتحان:")
    tw, th = get_text_metrics(draw, info_title, font_m)
    draw.text((1120 - int(tw), 145), info_title, fill="black", font=font_m)
    
    labels = [
        f"اسم الطالب: {user.get('name', 'غير محدد')}",
        f"المادة الدراسية: {info.get('subject_name', 'غير محدد')}",
        f"المرحلة / الصف: {info.get('stage', 'غير محدد')}",
        f"نموذج الأسئلة: {user.get('model_type', 'A')}"
    ]
    
    start_txt_y = 195
    for label in labels:
        txt = fix_arabic_text(label)
        tw, th = get_text_metrics(draw, txt, font_m)
        draw.text((1120 - int(tw), start_txt_y), txt, fill="black", font=font_m)
        draw.line([640, start_txt_y + 35, 1120, start_txt_y + 35], fill="#E0E0E0", width=1)
        start_txt_y += 55

    draw.rectangle([90, 130, 580, 450], outline="black", width=2)
    id_title = fix_arabic_text("بيانات التحقق الذكي (QR Code)")
    tw, th = get_text_metrics(draw, id_title, font_m)
    draw.text((335 - int(tw) // 2, 145), id_title, fill="black", font=font_m)
    
    if qr_path and os.path.exists(qr_path):
        qr_img = Image.open(qr_path).convert("RGB").resize((230, 230))
        img.paste(qr_img, (335 - 115, 195))


    note_y = 485
    note_txt = fix_arabic_text("يرجى تظليل الدائرة بشكل كامل مع الاهتمام بعدم خروج التظليلي عن الدائرة وكما في الامثلة :")
    tw_n, th_n = get_text_metrics(draw, note_txt, font_m)
    draw.text((1150, note_y), note_txt, fill="black", font=font_m, anchor="rm")

    ex_center_y = note_y - 2
    ex_x = 1150 - tw_n - 35 
    r = 12

    def draw_check(cx, cy):
        draw.line([(cx-5, cy), (cx-1, cy+5), (cx+7, cy-6)], fill="green", width=3)
        
    def draw_cross(cx, cy):
        draw.line([(cx-5, cy-5), (cx+5, cy+5)], fill="red", width=3)
        draw.line([(cx+5, cy-5), (cx-5, cy+5)], fill="red", width=3)


    draw.ellipse([ex_x - r*2, ex_center_y - r, ex_x, ex_center_y + r], fill="black", outline="black")
    draw_check(ex_x - r*2 - 15, ex_center_y)
    ex_x -= (r*2 + 55)


    draw.ellipse([ex_x - r*2, ex_center_y - r, ex_x, ex_center_y + r], outline="black", width=2)
    draw.chord([ex_x - r*2, ex_center_y - r, ex_x, ex_center_y + r], 0, 180, fill="black")
    draw_cross(ex_x - r*2 - 15, ex_center_y)
    ex_x -= (r*2 + 55)

    draw.ellipse([ex_x - r*2, ex_center_y - r, ex_x, ex_center_y + r], outline="black", width=2)
    cx, cy = ex_x - r, ex_center_y
    draw.line([cx-5, cy-5, cx+5, cy+5], fill="black", width=2)
    draw.line([cx+5, cy-5, cx-5, cy+5], fill="black", width=2)
    draw_cross(ex_x - r*2 - 15, ex_center_y)
    ex_x -= (r*2 + 55)

    # ---------------------------------------------

    start_y = 530 
    col_width = 265     
    row_height = 43 
    options = ['أ', 'ب', 'ج', 'د']
    right_margin_start = WIDTH - MARGIN
    q_bubble_radius = 13
    
    for i in range(100):
        col = i // 25
        row = i % 25
        
        col_right_x = right_margin_start - (col * col_width)
        q_y = start_y + (row * row_height)
        
        hindi_q_num = to_hindi_digits(i + 1)
        q_num_str = fix_arabic_text(f"({hindi_q_num})")

        center_y = q_y + q_bubble_radius
        draw.text((col_right_x - 5, center_y), q_num_str, fill="black", font=font_m, anchor="rm")
        
        bubble_start_x = col_right_x - 60
        for j, opt in enumerate(options):
            bx = bubble_start_x - (j * 46) - (q_bubble_radius * 2)
            by = q_y
            
            draw.ellipse([bx, by, bx + q_bubble_radius*2, by + q_bubble_radius*2], outline="black", width=1)
            
            opt_txt = fix_arabic_text(opt)
            draw.text((bx + q_bubble_radius, by + q_bubble_radius), opt_txt, fill="black", font=font_s, anchor="mm")
            
            master_coords.append({
                "q": i + 1,  
                "opt": opt,
                "bbox": [int(bx), int(by), int(bx + q_bubble_radius*2), int(by + q_bubble_radius*2)]
            })
            
    return [img], master_coords

def generate_all(target_dir='exam_sheets_pdf_output', Jsonpath=None, logo_path='logo.png'):
    if not os.path.exists(target_dir): 
        os.makedirs(target_dir)
    
    full_data = None
    if isinstance(Jsonpath, dict):
        full_data = Jsonpath
    elif isinstance(Jsonpath, str):
        if os.path.exists(Jsonpath):
            try:
                with open(Jsonpath, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)
            except Exception as e:
                print(f"Error reading JSON file '{Jsonpath}': {e}")
        elif Jsonpath.strip().startswith('{'):
            try:
                full_data = json.loads(Jsonpath)
            except Exception as e:
                print(f"Error parsing JSON string: {e}")

    if full_data is None:
        default_json = 'new_json.json'
        if os.path.exists(default_json):
            try:
                with open(default_json, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)
            except Exception as e:
                print(f"Error reading default JSON '{default_json}': {e}")
                return None
        else:
            print("No valid JSON input or file found.")
            return None

    data = full_data.get('data', [full_data])[0] if isinstance(full_data.get('data'), list) else full_data.get('data', full_data)
    
    info = {'stage': data.get('stage'), 'subject_name': data.get('subject')}
    master_coords, all_final_pages, temp_qrs = [], [], []
    
    f_l = load_font(FONT_PATH, 28)
    f_m = load_font(FONT_PATH, 20)
    f_s = load_font(FONT_PATH, 17)
    f_xs = load_font(FONT_PATH, 14)
    
    levelID = int(data.get('id', 681))
    
    try:
        for user in data.get('users', []):
            u_id = int(user.get('id', user.get('user_id', 59)))
            u_model = data.get('exam_info', {}).get('model_type', 'A')
            
            user_p = {
                'id': u_id, 
                'name': user.get('user_name', user.get('name', 'N/A')), 
                'model_type': u_model, 
                'exam': [(q if 'question' in q else {'question': q}) for q in user.get('exam', [])]
            }
            
            qr_p = os.path.join(target_dir, f"qr_{u_id}_{uuid.uuid4().hex[:6]}.png")
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
            
            bubble_pages, current_coords = create_bubble_sheet_and_map(info, user_p, qr_p, f_l, f_m, f_xs, logo_path=logo_path)
            all_final_pages.extend(bubble_pages) 
            
            exam_pages = create_exam_pages(info, user_p, f_l, f_m, f_s)
            all_final_pages.extend(exam_pages)
            
            if len(current_coords) > len(master_coords):
                master_coords = current_coords
                
        if all_final_pages:
            pdf_path = os.path.join(target_dir, "All_Students_Exams.pdf")
            all_final_pages[0].save(pdf_path, save_all=True, append_images=all_final_pages[1:], resolution=150.0)
            
            json_out_path = os.path.join(target_dir, "unified_master_map.json")
            with open(json_out_path, 'w', encoding='utf-8') as f:
                json.dump(master_coords, f, ensure_ascii=False, indent=4)

            return {"pdf_path": pdf_path, "json_path": json_out_path}
            
    finally:
        for qp in temp_qrs:
            if os.path.exists(qp): 
                try:
                    os.remove(qp)
                except Exception:
                    pass
    
    return None

if __name__ == '__main__':
    generate_all()