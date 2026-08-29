import os
import shutil
import json
import uuid
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from fastapi.concurrency import run_in_threadpool
from generate_exams import generate_all 
from omr_scanner import process_omr_smart, debug_omr_coords

app = FastAPI(title="OMR & Exam System API")

def cleanup_path(path: str):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Cleanup Error: {e}")

@app.post("/generate-exams")
async def api_generate_exams(payload: dict): 
    actual_data = payload
    if "data_level" not in payload and "data_exams" not in payload:
        if "data" in payload and isinstance(payload["data"], dict):
            actual_data = payload["data"]
        elif "data" in payload and isinstance(payload["data"], list) and len(payload["data"]) > 0:
            actual_data = payload["data"][0]

    if "data_level" in actual_data and "data_exams" in actual_data:
        exam_info_data = actual_data["data_level"].get("exam_info", {})
        start_time = exam_info_data.get("start_time", "2026-06-18T10:00:00.000000Z")
        
        transformed_data = {
            "id": actual_data["data_level"].get("id"),
            "stage": actual_data["data_level"].get("stage"),
            "subject": actual_data["data_level"].get("subject"),
            "exam_info": {
                "testing_method": exam_info_data.get("testing_method", "online"),
                "model_type": exam_info_data.get("model_type", "random"),
                "number_of_groups": exam_info_data.get("number_of_groups", 1),
                "number_of_questions": exam_info_data.get("number_of_questions", 4),
                "is_active": exam_info_data.get("is_active", True),
                "attempt_limit": exam_info_data.get("attempt_limit", 1),
                "start_time": start_time,
                "end_time": start_time
            },
            "users": []
        }
        
        for item in actual_data.get("data_exams", []):
            user_obj = {
                "user_id": item.get("user_id"),
                "user_name": item.get("user_name"),
                "name": item.get("user_name"), 
                "exam": []
            }
            
            for q in item.get("questions", []):
                formatted_options = []
                for opt in q.get("options", []):
                    formatted_options.append({
                        "text": opt.get("text", ""),
                        "files": [] 
                    })
                
                q_text = q.get("question_text", {})
                if isinstance(q_text, dict):
                    q_text_str = q_text.get("text", "")
                else:
                    q_text_str = str(q_text)

                user_obj["exam"].append({
                    "question_id": q.get("id"),
                    "answer": None,
                    "ResponseTime": None,
                    "state": "pending",
                    "question": {
                        "id": q.get("id"),
                        "question_text": {
                            "text": q_text_str,
                            "files": []
                        },
                        "question_type": q.get("question_type", "options"),
                        "question_type_translation": "خيارات",
                        "options": formatted_options,
                        "correct_answer": "1", 
                        "status": "Accepting",
                        "status_translation": "قبول",
                        "status_options": ["Reviewing"],
                        "notes": None
                    }
                })
            transformed_data["users"].append(user_obj)
            
        data_to_process = transformed_data
        
    elif "users" in actual_data:
        data_to_process = actual_data
    else:
        raise HTTPException(status_code=400, detail="Invalid JSON format: Could not find 'data_level' and 'data_exams', nor 'users'. Please check Postman payload.")

    request_id = str(uuid.uuid4())[:8]
    base_temp_dir = os.path.join(os.getcwd(), "temp_storage")
    unique_path = os.path.join(base_temp_dir, f"task_{request_id}")
    os.makedirs(unique_path, exist_ok=True)
    
    input_json_path = os.path.join(unique_path, "input_data.json")
    with open(input_json_path, "w", encoding='utf-8') as f:
        json.dump(data_to_process, f, ensure_ascii=False, indent=4)

    pdf_filename = "All_Students_Exams.pdf"
    pdf_full_path = os.path.join(unique_path, pdf_filename)
    map_filename = "unified_master_map.json"
    map_full_path = os.path.join(unique_path, map_filename)

    try:
        result = await run_in_threadpool(
            generate_all, 
            target_dir=unique_path, 
            Jsonpath=input_json_path
        )

        if not result:
            raise HTTPException(status_code=500, detail="PDF generation returned None. Check if the generated users array is empty.")
            
        if not os.path.exists(pdf_full_path):
            raise HTTPException(status_code=500, detail="PDF was generated but not found in the target directory.")

        static_map_path = os.path.join(os.getcwd(), "unified_master_map.json")
        if os.path.exists(map_full_path):
            shutil.copy(map_full_path, static_map_path)

        return FileResponse(
            path=pdf_full_path, 
            media_type='application/pdf', 
            filename=pdf_filename,
            background=BackgroundTask(cleanup_path, unique_path)
        )

    except HTTPException:
        cleanup_path(unique_path)
        raise
    except Exception as e:
        cleanup_path(unique_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scan-sheet")
async def api_scan_sheet(file: UploadFile = File(...)):
    unique_id = str(uuid.uuid4())[:8]
    temp_img_path = f"temp_scan_{unique_id}_{file.filename}"
    master_map = "unified_master_map.json"
    debug_img_path = f"debug_{unique_id}.jpg"
    
    if not os.path.exists(master_map):
        raise HTTPException(status_code=400, detail="Map file not found")

    with open(temp_img_path, "wb") as buffer: 
        shutil.copyfileobj(file.file, buffer)
        
    try:
        await run_in_threadpool(debug_omr_coords, temp_img_path, master_map, debug_img_path)
        results = await run_in_threadpool(process_omr_smart, temp_img_path, master_map)
        
        if results is None or "error" in results:
            raise HTTPException(status_code=400, detail="Scanning failed")
            
        return JSONResponse(content=results)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if os.path.exists(temp_img_path): 
            os.remove(temp_img_path)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8801)