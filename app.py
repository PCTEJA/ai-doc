
import requests
import secrets
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import io
from flask import Flask, render_template, request, jsonify, send_file
import os
import git
import openai
import tempfile
import markdown
from flask_session import Session

# starting flask baby
app = Flask(__name__)
sess = Session()


api_key = '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'
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['GITHUB_CLIENT_ID'] = '66c0b9f99e76f95951f1'
app.config['GITHUB_CLIENT_SECRET'] = '955dc458fd868d8157717e658c8fb6dc99f1c427'
app.config['SESSION_TYPE'] = 'filesystem'
# session(app)
sess.init_app(app)

@app.route('/login-with-github')
def login_with_github():
    if 'access_token' not in session:
        print("No access token found")
        github_authorize_url = 'https://github.com/login/oauth/authorize'
        return redirect(f'{github_authorize_url}?client_id={app.config["GITHUB_CLIENT_ID"]}&scope=repo')
    else:
        return redirect(url_for('index'))


@app.route('/github-callback')
def github_callback():
    code = request.args.get('code')
    github_token_url = 'https://github.com/login/oauth/access_token'
    post_data = {
        'client_id': app.config['GITHUB_CLIENT_ID'],
        'client_secret': app.config['GITHUB_CLIENT_SECRET'],
        'code': code
    }
    headers = {'Accept': 'application/json'}
    result = requests.post(github_token_url, data=post_data, headers=headers)
    result_json = result.json()
    access_token = result_json['access_token']
    session['access_token'] = access_token
    return redirect(url_for('list_repos'))


@app.route('/list-repos')
def list_repos():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login_with_github'))

    headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    repos_result = requests.get(
        'https://api.github.com/user/repos', headers=headers)
    repos_json = repos_result.json()

    for repo in repos_json:
        languages_url = repo['languages_url']
        languages_result = requests.get(languages_url, headers=headers)
        languages_json = languages_result.json()

        if languages_json:
            most_used_language = max(languages_json, key=languages_json.get)
            repo['most_used_language'] = most_used_language
        else:
            repo['most_used_language'] = 'None'

    language_stats = calculate_language_stats(repos_json)
    total_count = len(repos_json)
    return render_template(
        'list_repos.html',
        repos=repos_json,
        language_stats=language_stats,
        total_count=total_count
    )


def calculate_language_stats(repos):
    language_data = {}

    for repo in repos:
        language = repo.get('language', 'Unknown')
        language_data[language] = language_data.get(language, 0) + 1

    language_stats = []
    total_repos = sum(language_data.values())
    for language, count in language_data.items():
        language_stats.append({
            'name': language,
            'percentage': (count / total_repos) * 100
        })

    return language_stats


@app.route('/')
def index():
    return render_template('home.html')

# brain


def chat_gpt_for_user_manual(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system",
                "content": "I want you to provide me a Professional User Manual for the Provided Program"},
            {"role": "user", "content": prompt}
        ],
        api_key=api_key
    )
    return response


def chat_gpt_for_documentation(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system",
                "content": "I want you to provide me a Professional Technical Documentation for the Provided Program"},
            {"role": "user", "content": prompt}
        ],
        api_key=api_key
    )
    return response


@app.route('/generate-manual', methods=['POST'])
def generate_user_manual():
    try:
        all_python_files_code = session.get('all_python_files_code', None)
        if (all_python_files_code == None):
            content = request.form['github_link']
            github_link = content
            with tempfile.TemporaryDirectory() as tmpdirname:
                git.Repo.clone_from(github_link, tmpdirname)
                all_python_files_code = ""
                for subdir, dirs, files in os.walk(tmpdirname):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(subdir, file)
                            with open(file_path, 'r') as code_file:
                                code = code_file.read()
                                all_python_files_code += f"File: {file}\n{code}\n\n"
        session['all_python_files_code'] = all_python_files_code
        user_manual_response = chat_gpt_for_user_manual(all_python_files_code)

        user_manual = markdown.markdown(
            user_manual_response.choices[0].message.content)
        session['usermkd'] = user_manual_response.choices[0].message.content
        user_manual_file = io.BytesIO(user_manual.encode('utf-8'))
        user_manual_file.seek(0)

        session['user_manual'] = user_manual
        return redirect(url_for('view_user_manual'))

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download-doc', methods=['GET'])
def download_documentation():
    documentation = session.get('markedown_format', None)
    if documentation:
        documentation_file = io.BytesIO(documentation.encode('utf-8'))
        documentation_file.seek(0)
        return send_file(documentation_file, as_attachment=True, download_name='documentation.txt')
    else:
        return "No documentation available to download.", 404


@app.route('/download-user', methods=['GET'])
def download_user():
    documentation = session.get('user_manual', None)
    if documentation:
        documentation_file = io.BytesIO(documentation.encode('utf-8'))
        documentation_file.seek(0)
        return send_file(documentation_file, as_attachment=True, download_name='user_manual.txt')
    else:
        return "No documentation available to download.", 404

# body


@app.route('/generate-doc', methods=['POST'])
def generate_documentation():
    content = request.form['github_link']
    github_link = content
    try:
        all_python_files_code = session.get('all_python_files_code', None)
        if (all_python_files_code == None):
            with tempfile.TemporaryDirectory() as tmpdirname:
                git.Repo.clone_from(github_link, tmpdirname)
                all_python_files_code = ""
                for subdir, dirs, files in os.walk(tmpdirname):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(subdir, file)
                            with open(file_path, 'r') as code_file:
                                code = code_file.read()
                                all_python_files_code += f"File: {file}\n{code}\n\n"
        session['all_python_files_code'] = all_python_files_code
        response = chat_gpt_for_documentation(all_python_files_code)
        mkd = response.choices[0].message.content
        documentation = markdown.markdown(
            response.choices[0].message.content)

        documentation_file = io.BytesIO(documentation.encode('utf-8'))
        documentation_file.seek(0)
        session['documentation'] = documentation
        session['markedown_format'] = mkd
        session['all_python_files_code'] = all_python_files_code
        return redirect(url_for('view_documentation'))

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/home', methods=['GET'])
def home():
    return render_template('home.html')


@app.route('/view-doc', methods=['GET'])
def view_documentation():
    documentation = session.get('documentation', None)
    mkd = session.get('markedown_format', None)
    if documentation:
        return render_template('documentation.html', documentation=documentation, mkd=mkd)
    else:
        return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/profile')
def profile():
    if 'access_token' not in session:
        return redirect(url_for('login_with_github'))
    else:
        return redirect(url_for('list_repos'))


@app.route('/view-manual', methods=['GET'])
def view_user_manual():
    user_manual = session.get('user_manual', None)
    if user_manual:
        return render_template('user_manual.html', user_manual=user_manual)
    else:
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
