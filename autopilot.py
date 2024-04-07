import streamlit as st
import multion
from interpreter import interpreter
import os
import tempfile
import keyboard
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
from threading import Thread

# Initialize OpenAI client
openai_client = OpenAI()
multion_api_key = 'YOUR_MULTION_API_KEY'

st.set_page_config(page_title="AUTOPILOT FOR YOUR DESKTOP", page_icon=":robot_face:", layout="wide")

hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

st.markdown(
    """
    <div style='backgroundColor:white;padding:16px;border-radius:16px'>
    <h1 style='text-align:center;color:black;'>AutoPilot For Your Desktop</h1>
    </div>
    """,
    unsafe_allow_html=True
)


multion.login(use_api=True, multion_api_key=multion_api_key)

class Assistants:
    def __init__(self):
        self.recording = None
        self.initialize_session_state()

    def initialize_session_state(self):
        if 'conversation' not in st.session_state:
            st.session_state['conversation'] = []
        if 'last_execution_result' not in st.session_state:
            st.session_state['last_execution_result'] = None
        if 'web_bot_session_id' not in st.session_state:
            st.session_state['web_bot_session_id'] = None
        if 'web_bot_conversation' not in st.session_state:
            st.session_state['web_bot_conversation'] = []
        if 'prompt' not in st.session_state:
            st.session_state['prompt'] = ""

    def display_conversation_history(self):
        for message in st.session_state['conversation']:
            st.write(message)

    def start_recording_audio(self):
        """
        Starts recording audio.
        """
        print("Recording...")
        # Recording parameters
        fs = 44100  # Sample rate
        seconds = 10  # Recording duration

        # Record audio
        self.recording = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="int16")

    def stop_recording_audio(self):
        """
        Stops recording audio.
        """
        print("Recording Stopped")
        sd.stop()  # Stop the recording

    def transcribe_audio(self, input_key):
        """
        Transcribes the recorded audio using OpenAI.
        """
        if self.recording is not None:
            print("Transcribing...")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
                temp_audio_path = temp_audio_file.name
                sf.write(temp_audio_path, self.recording, 44100)

            with open(temp_audio_path, "rb") as audio_file:
                transcription = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
                transcript = transcription.text

            # Cleanup: Delete the temporary audio file
            os.remove(temp_audio_path)

            # Update the prompt in the corresponding text area
            st.session_state['prompt'] = transcript
            st.text_area("", value=st.session_state['prompt'], placeholder="Type your message here...", key=input_key, height=100)

    def chat_with_assistant(self):
        self.display_conversation_history()

        with st.container():
            col1, col2 = st.columns([1, 3])

            with col1:
                start_recording = st.button("Start Recording")
                stop_recording = st.button("Stop Recording")

            with col2:
                prompt = st.text_area("", value=st.session_state['prompt'], placeholder="Type your message here...", key="chat_input", height=100)
                submit_button = st.button("Send", use_container_width=True)

            if start_recording:
                self.start_recording_audio()

            if stop_recording:
                self.stop_recording_audio()
                self.transcribe_audio("chat_input")  # Transcribe directly after stopping recording

            if submit_button and prompt:
                if prompt.lower() == 'exit':
                    st.write("Goodbye!")
                    self.initialize_session_state()
                else:
                    self.process_user_message(prompt)

    def process_user_message(self, prompt):
        # Display the user's prompt
        user_message = f"You: {prompt}"
        st.write(user_message)
        st.session_state['conversation'].append(user_message)

        interpreter.llm.model = "gpt-3.5-turbo"
        interpreter.custom_instructions = "Remember that my OS is Windows 11 and if ask you anything about then don't write code that is used in Mac or Linux because it won't work.and My Desktop Folder is in OneDrive Folder."
        interpreter.auto_run = True
        result = interpreter.chat(prompt)  # Call the interpreter with the new prompt
        # Store the entire result
        st.session_state['last_execution_result'] = result

        # Display the assistant's response
        self.display_assistant_response(result)

    def display_assistant_response(self, result):
        if len(result):
            result_content = result[-1]['content']

        assistant_message = f"Assistant: {result_content}"
        st.write(assistant_message)
        st.session_state['conversation'].append(assistant_message)

        # Add copy button for the result
        if result_content:
            copy_button_html = f"""
                <button onclick="copyText('{result_content}')" style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">
                    Copy Result
                </button>
                <script>
                function copyText(text) {{
                    navigator.clipboard.writeText(text);
                    alert("Text copied to clipboard!");
                }}
                </script>
            """
            st.markdown(copy_button_html, unsafe_allow_html=True)

    def run_web_bots(self, prompt):
        """Runs web bots based on the given prompt"""
        multion.login(use_api=True, multion_api_key=multion_api_key)

        if st.session_state['web_bot_session_id']:
            session_id = st.session_state['web_bot_session_id']
        else:
            response = multion.create_session({"url": "https://google.com"})
            session_id = response['session_id']
            st.session_state['web_bot_session_id'] = session_id

        while True:
            res = multion.step_session(session_id, {"input": prompt, "url": "https://www.google.com", "includeScreenshot": False})

            if res['status'] == 'DONE':
                print("Task Completed!\nNow, how can I assist you further?\n")
                assistant_response = f"Task completed successfully.\n\nHere's how the task was performed:\n{res['message']}"
                st.session_state['web_bot_conversation'].append(f"You: {prompt}")
                st.session_state['web_bot_conversation'].append(f"Assistant: {assistant_response}")
                st.write(f"Assistant: {assistant_response}")
                break

            elif res['status'] in ['RUNNING', 'CONTINUE']:
                if res['status'] == 'RUNNING':
                    st.session_state['web_bot_conversation'].append("Assistant: Task in progress...")
                    st.write("Assistant: Task in progress...")
                elif res['status'] == 'CONTINUE':
                    continue
                else:
                    st.write(f"Error: {res['message']}")
                    break

    def web_bots_in_action(self):
        for message in st.session_state['web_bot_conversation']:
            st.write(message)

        with st.container():
            col1, col2 = st.columns([1, 3])

            with col1:
                start_recording = st.button("Start Recording")
                stop_recording = st.button("Stop Recording")

            with col2:
                prompt = st.text_area("", value=st.session_state['prompt'], placeholder="Enter your prompt here...", key="web_bot_input", height=100)
                submit_button = st.button("Send", use_container_width=True)
                exit_button = st.button("Exit", use_container_width=True)

            if start_recording:
                self.start_recording_audio()

            if stop_recording:
                self.stop_recording_audio()
                self.transcribe_audio("web_bot_input")  # Transcribe directly after stopping recording

            if exit_button:
                st.write("Exiting WebBot...")
                if st.session_state['web_bot_session_id']:
                    multion.close_session(st.session_state['web_bot_session_id'])
                self.initialize_session_state()

            if submit_button and prompt:
                st.session_state['web_bot_conversation'].append(f"You: {prompt}")
                st.write(f"You: {prompt}")
                self.run_web_bots(prompt)

assistant = Assistants()

col1, col2 = st.columns([1, 3])

with col1:
    choice = st.selectbox('Choose an option', ['Autopilot for your daily tasks', 'WebBots in Action', 'Exit'])

if choice == 'Autopilot for your daily tasks':
    with col2:
        assistant.chat_with_assistant()

elif choice == 'WebBots in Action':
    with col2:
        assistant.web_bots_in_action()

elif choice == 'Exit':
    st.write("Goodbye!")
    st.stop()

if st.session_state['last_execution_result']:
    st.write("Last Execution Result:")
    st.write(st.session_state['last_execution_result'])
