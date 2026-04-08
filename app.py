from flask import Flask, render_template, request, jsonify, Response, send_file
import time
import json
import io
import scraper
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start():
    data = request.json
    modo = data.get('modo')
    user_input = data.get('user_input')
    is_link = data.get('is_link', True)
    
    if not modo or not user_input:
        return jsonify({'error': 'Parâmetros ausentes'}), 400
        
    try:
        job_id = scraper.start_extraction(modo, user_input, is_link)
        return jsonify({'job_id': job_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview', methods=['POST'])
def preview():
    data = request.json
    modo = data.get('modo')
    user_input = data.get('user_input')
    
    if not modo or not user_input:
        return jsonify({'error': 'Parâmetros ausentes'}), 400
        
    try:
        preview_data = scraper.preview_project(modo, user_input)
        return jsonify(preview_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/progress/<job_id>')
def progress(job_id):
    def event_stream():
        while True:
            job = scraper.get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
                
            data = {
                'status': job['status'],
                'progress_percent': job['progress_percent'],
                'info': job['info']
            }
            
            yield f"data: {json.dumps(data)}\n\n"
            
            if job['status'] in ['completed', 'error']:
                break
                
            time.sleep(0.5)

    return Response(event_stream(), content_type='text/event-stream')

@app.route('/api/download/<job_id>')
def download(job_id):
    job = scraper.get_job(job_id)
    if not job or job['status'] != 'completed':
        return "Arquivo não disponível ou job não encontrado", 404
        
    file_data = job['result_bytes']
    filename = job['filename']
    
    return send_file(
        io.BytesIO(file_data),
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
