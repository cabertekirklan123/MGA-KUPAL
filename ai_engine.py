"""
AI Engine for EchoHUD.
Supports streaming responses from:
1. Demo / Simulation Mode (instant testing, no API key needed)
2. Google Gemini API (gemini-2.0-flash, gemini-1.5-flash, supports vision)
3. Groq Cloud API (llama-3.3-70b-versatile, llama-3.1-8b-instant)
4. OpenAI API (gpt-4o-mini, gpt-4o)
5. Ollama Local API (llama3.2, mistral, etc.)
"""

import time
import json
import base64
import requests
from config import get_active_system_prompt

MOCK_DATABASE = [
    {
        "keywords": ["react", "virtual dom", "hooks", "state"],
        "answer": (
            "• **Core Concept**: Virtual DOM is an in-memory lightweight representation of the real DOM.\n"
            "• **Reconciliation**: Uses diffing algorithm (O(n)) to find changed nodes, batching updates to minimize expensive DOM reflows.\n"
            "• **Fiber Architecture**: Introduced in React 16 to enable incremental rendering, pause/resume work, and prioritize critical updates.\n"
            "• **Key Hook Rules**: Only call hooks at top level, only call from React function components."
        )
    },
    {
        "keywords": ["database", "index", "b-tree", "b+tree", "sql"],
        "answer": (
            "• **Structure**: Databases use B+ Trees because all data pointers reside in leaf nodes, linked sequentially.\n"
            "• **Advantages**: Exceptional range-query performance, predictable O(log N) lookups, high fan-out reduces disk I/O.\n"
            "• **Trade-offs**: Speeds up SELECT queries significantly, but introduces overhead on INSERT, UPDATE, and DELETE due to tree rebalancing.\n"
            "• **Best Practice**: Index high-cardinality columns used in WHERE/JOIN clauses; avoid indexing frequently mutated low-cardinality fields."
        )
    },
    {
        "keywords": ["cap", "distributed", "system", "acid", "consistency"],
        "answer": (
            "• **CAP Theorem**: In a network partition (P), a distributed system must choose between Consistency (C) and Availability (A).\n"
            "• **CP Systems** (e.g. HBase, CockroachDB): Reject writes or wait when nodes are partitioned to guarantee fresh data.\n"
            "• **AP Systems** (e.g. Cassandra, DynamoDB): Accept writes everywhere, resolving conflicts via eventual consistency / CRDTs.\n"
            "• **PACELC Extension**: Even without partitions, trades off Latency (L) versus Consistency (C)."
        )
    },
    {
        "keywords": ["two sum", "algorithm", "array", "leetcode", "hash"],
        "answer": (
            "• **Optimal Approach**: One-pass Hash Map storing `target - num` as key and current index as value.\n"
            "• **Complexity**: Time Complexity is O(n), Space Complexity is O(n).\n"
            "• **Edge Cases**: Negative numbers, duplicate values, no valid pair exists.\n"
            "• **Python Snippet**:\n"
            "```python\n"
            "seen = {}\n"
            "for i, n in enumerate(nums):\n"
            "    diff = target - n\n"
            "    if diff in seen: return [seen[diff], i]\n"
            "    seen[n] = i\n"
            "```"
        )
    },
    {
        "keywords": ["how's your day", "how is your day", "how are you", "how are you doing", "how's everything", "how has your day been"],
        "answer": (
            "I'm doing great, thank you Zara! It's been a smooth and relaxing day so far, and I'm really excited for our interview today. How about you, how is your day going?"
        )
    },
    {
        "keywords": ["can you hear me", "hear me clearly", "can you see me", "ready to begin", "ready to start", "ready for the interview"],
        "answer": (
            "Yes, I can hear you loud and clear, Zara, and I'm ready whenever you are."
        )
    },
    {
        "keywords": ["for a living", "what do you do", "tell me about yourself", "your background", "who are you"],
        "answer": (
            "I am an IT student and remote contractor specializing in AI data evaluation, multimodal labeling, and quality assurance. At Outlier AI, I evaluate multimodal model outputs across video, audio, and text to catch hallucinations, and at Remotasks, I annotate video movement data for AI systems. I bring a rigorous QA mindset and strict adherence to project rubrics to ensure clean, reliable data."
        )
    },
    {
        "keywords": ["strength", "weakness", "greatest strength"],
        "answer": (
            "My greatest strength is my attention to detail and my discipline in following project guidelines without guessing. Coming from a software QA background, I treat data labeling like rigorous testing, catching subtle edge-case errors while keeping my quality consistent across high volumes."
        )
    },
    {
        "keywords": ["ai slop", "artificial text", "detect ai", "hallmarks of ai"],
        "answer": (
            "When identifying AI-generated text, I look for telltale buzzwords like delve or tapestry, overly repetitive sentence rhythm, and a lack of real substance. AI writing often sounds grammatically polished on the surface, but it lacks specific human examples and real-world nuance."
        )
    },
    {
        "keywords": ["assess", "editorial judgment", "evaluate content", "quality assessment"],
        "answer": (
            "My evaluation approach centers on clarity, logical flow, and clean grammar. I ensure thoughts connect smoothly without contradictions, tighten wordy sentences, and confirm that the tone is natural and credible for the intended audience."
        )
    },
    {
        "keywords": ["constructive feedback", "feedback on writing", "how do you give feedback"],
        "answer": (
            "When giving feedback, I point out the exact line or issue directly and explain why it feels unnatural or unclear. Then I provide a concrete, actionable edit that improves clarity while keeping the original intent intact."
        )
    },
    {
        "keywords": ["video annotation", "data labeling", "audio annotation", "labeling experience"],
        "answer": (
            "I have hands-on experience annotating video and audio datasets for training AI models. At Outlier AI and Remotasks, I labeled movement and multimedia content using frame-accurate timestamps, strictly adhering to taxonomy guidelines and documenting any borderline cases with clear notes."
        )
    },
    {
        "keywords": ["guideline-based", "follow guidelines", "instruction following", "ambiguous", "edge case"],
        "answer": (
            "I always follow written project rubrics objectively rather than relying on personal assumptions. Whenever I encounter blurry or borderline footage, I never guess; instead, I flag it directly to the project coordinator with exact timestamps and clear notes."
        )
    },
    {
        "keywords": ["attention to detail", "spotting errors", "ensure quality", "accuracy"],
        "answer": (
            "In video and audio annotation, I focus on frame accuracy and catching subtle flaws like audio-visual desync, boundary bleed, or inaccurate AI descriptions. As a BSIT student with a QA mindset, I pace my work carefully so my labeling accuracy stays high across the entire session."
        )
    },
    {
        "keywords": ["content moderation", "inappropriate", "safety standards", "compliance", "confidentiality"],
        "answer": (
            "I evaluate content strictly against established safety standards without personal bias. When flagging non-compliant media, I write clear objective rationales citing the exact policy, and I handle all client data with complete confidentiality."
        )
    },
    {
        "keywords": ["isaac sim", "gazebo", "mujoco", "pybullet", "simulation platform", "simulation engine"],
        "answer": (
            "I have hands-on experience setting up 3D assets and environments in Isaac Sim, Gazebo, and MuJoCo. In Isaac Sim, I import USD models, build tabletop scenes, and check basic physics stability, while in Gazebo and MuJoCo I work with URDF and MJCF files to test joints, collisions, and object interactions."
        )
    },
    {
        "keywords": ["real to sim", "3d asset", "collision mesh", "visual mesh", "cad", "modeling"],
        "answer": (
            "When preparing 3D models for simulation, I separate the visual mesh from the collision geometry. I keep the visual model clean while simplifying the collision hull into convex shapes or basic primitives, which prevents physics lag and stops objects from snagging or clipping through surfaces."
        )
    },
    {
        "keywords": ["friction", "mass", "inertia", "physics parameter", "tuning", "rigid body", "material property"],
        "answer": (
            "I calibrate physical properties by setting accurate mass, center of mass, and friction values based on real object specs. I also tune joint damping and restitution so objects slide, collide, and come to rest naturally without unnatural shaking or bouncing."
        )
    },
    {
        "keywords": ["sim to real", "discrepancy", "troubleshoot", "troubleshooting", "domain randomization", "gap"],
        "answer": (
            "When troubleshooting simulation glitches like jitter or mesh penetration, I adjust collision margins, increase physics substeps, and clean up messy geometry. I also test slight variations in friction and object placement to make sure the simulated environment remains stable."
        )
    },
    {
        "keywords": ["graphic design", "design tools", "figma", "photoshop", "illustrator", "design experience"],
        "answer": (
            "I design primarily in Figma and Adobe Creative Suite, focusing on clean digital layouts, responsive vector assets, and structured brand assets. I use Figma for rapid prototyping, component systems, and vector frames, while leveraging Illustrator for scalable vector artwork and Photoshop for high-detail raster compositions."
        )
    },
    {
        "keywords": ["visual hierarchy", "typography", "color theory", "contrast", "composition", "layout"],
        "answer": (
            "My design philosophy is grounded in strong visual hierarchy, where scale, weight, and contrast guide the viewer's eye to the most important message first. I pair fonts thoughtfully to balance readability and personality, utilize grid systems with intentional white space, and ensure all color palettes meet high accessibility standards."
        )
    },
    {
        "keywords": ["design critique", "critique graphics", "giving feedback", "design feedback", "evaluate graphic"],
        "answer": (
            "When critiquing visual assets, I focus on actionable and objective feedback by evaluating layout balance, typography legibility, and brand alignment. Rather than vague aesthetic opinions, I highlight specific issues like crowded padding or weak contrast, then provide concrete visual solutions that improve user clarity."
        )
    },
    {
        "keywords": ["creative decisions", "design rationale", "why did you choose", "methodology"],
        "answer": (
            "I always document the rationale behind my creative decisions, connecting every choice of color, typography, and layout directly to user needs and project goals. This transparent documentation helps stakeholders understand the strategy behind the visuals and ensures smooth handoffs across collaborative review cycles."
        )
    }
]


class AIEngine:
    def __init__(self, config):
        self.config = config

    def ask(self, question, image_bytes=None, on_token=None):
        """
        Queries the configured AI provider with streaming token output.
        :param question: Detected question or text prompt
        :param image_bytes: Optional screenshot bytes for vision analysis
        :param on_token: callback(token_str) fired as text streams
        :return: full response text
        """
        provider = self.config.get("ai_provider", "demo")
        system_prompt = get_active_system_prompt(self.config)

        if provider == "demo":
            return self._ask_demo(question, on_token)
        elif provider == "gemini":
            return self._ask_gemini(question, system_prompt, image_bytes, on_token)
        elif provider == "groq":
            if image_bytes and self.config.get("gemini_api_key"):
                # Groq text model doesn't support images; route screenshot to Gemini Vision
                return self._ask_gemini(question, system_prompt, image_bytes, on_token)
            return self._ask_groq(question, system_prompt, on_token)
        elif provider == "openai":
            return self._ask_openai(question, system_prompt, image_bytes, on_token)
        elif provider == "ollama":
            return self._ask_ollama(question, system_prompt, on_token)
        else:
            return self._ask_demo(question, on_token)

    def _ask_demo(self, question, on_token):
        """Generates contextual simulated response with live streaming animation."""
        q_lower = question.lower()
        matched_answer = None

        for item in MOCK_DATABASE:
            if any(k in q_lower for k in item["keywords"]):
                matched_answer = item["answer"]
                break

        if not matched_answer:
            # Context-sensitive fallback
            if any(w in q_lower for w in ["who", "what do you", "tell me", "career", "work", "job"]):
                matched_answer = (
                    "I work as an IT student and remote contractor specializing in AI data evaluation, multimodal labeling, and quality assurance. I focus on frame-accurate video annotation, catching subtle inconsistencies, and following detailed project rubrics to provide clean, reliable training data."
                )
            else:
                matched_answer = (
                    f"Regarding {question.strip()[:40]}, I focus on following the project guidelines strictly and verifying every detail objectively. I ensure all edge cases are documented with clear rationale so the data remains consistent and accurate."
                )

        full_text = ""
        # Simulate realistic token streaming
        words = matched_answer.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            full_text += token
            if on_token:
                on_token(token)
            time.sleep(0.02)
        return full_text

    def _ask_gemini(self, question, system_prompt, image_bytes, on_token):
        """Streaming query to Google Gemini API with robust non-streaming fallback."""
        api_key = self.config.get("gemini_api_key", "").strip()
        if not api_key:
            err = "[Error] Gemini API key is missing. Add it in Settings."
            if on_token: on_token(err)
            return err

        model = self.config.get("selected_model", {}).get("gemini", "gemini-3.8-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={api_key}&alt=sse"

        parts = [{"text": f"System Context:\n{system_prompt}\n\nInterviewer Question:\n{question}"}]
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": b64_img
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800}
        }

        # For image/vision requests, non-streaming generateContent is faster and more reliable
        if image_bytes:
            vision_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                res = requests.post(vision_url, json=payload, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text_part:
                            words = text_part.split(" ")
                            for i, word in enumerate(words):
                                token = word + (" " if i < len(words) - 1 else "")
                                full_text += token
                                if on_token: on_token(token)
                                time.sleep(0.015)
                            return full_text
                print(f"[Gemini Vision] HTTP {res.status_code}: {res.text[:150]}")
            except Exception as e:
                print(f"[Gemini Vision Error]: {e}")
            return self._ask_demo(question, on_token)

        full_text = ""
        try:
            res = requests.post(url, json=payload, stream=True, timeout=12)
            if res.status_code != 200:
                print(f"[Gemini Stream] HTTP {res.status_code}, trying non-streaming generateContent...")
                fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                res_nonstream = requests.post(fallback_url, json=payload, timeout=15)
                if res_nonstream.status_code == 200:
                    data = res_nonstream.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text_part:
                            words = text_part.split(" ")
                            for i, word in enumerate(words):
                                token = word + (" " if i < len(words) - 1 else "")
                                full_text += token
                                if on_token: on_token(token)
                                time.sleep(0.015)
                            return full_text

                # If Groq is available and no image, fallback to Groq
                if not image_bytes and self.config.get("groq_api_key"):
                    if on_token:
                        on_token("*(Gemini busy. Switching to Groq...)*\n\n")
                    return self._ask_groq(question, system_prompt, on_token)
                else:
                    return self._ask_demo(question, on_token)

            for line in res.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_json = line_str[6:]
                    try:
                        chunk = json.loads(data_json)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if text_part:
                                full_text += text_part
                                if on_token:
                                    on_token(text_part)
                    except Exception:
                        pass
            return full_text
        except Exception as e:
            print(f"[Gemini Error]: {e}")
            if self.config.get("groq_api_key"):
                return self._ask_groq(question, system_prompt, on_token)
            return self._ask_demo(question, on_token)

    def _ask_groq(self, question, system_prompt, on_token):
        """Streaming query to Groq Cloud API."""
        api_key = self.config.get("groq_api_key", "").strip()
        if not api_key:
            err = "[Error] Groq API key is missing. Add it in Settings."
            if on_token: on_token(err)
            return err

        model = self.config.get("selected_model", {}).get("groq", "openai/gpt-oss-20b")
        if "llama-3" in model:
            model = "openai/gpt-oss-20b"
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
            "stream": True
        }

        return self._stream_openai_compatible(url, headers, payload, on_token)

    def _ask_openai(self, question, system_prompt, image_bytes, on_token):
        """Streaming query to OpenAI API."""
        api_key = self.config.get("openai_api_key", "").strip()
        if not api_key:
            err = "[Error] OpenAI API key is missing. Add it in Settings."
            if on_token: on_token(err)
            return err

        model = self.config.get("selected_model", {}).get("openai", "gpt-4o-mini")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        user_content = question
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            user_content = [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
            ]

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.3,
            "max_tokens": 600,
            "stream": True
        }

        return self._stream_openai_compatible(url, headers, payload, on_token)

    def _ask_ollama(self, question, system_prompt, on_token):
        """Streaming query to local Ollama."""
        base_url = self.config.get("ollama_url", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/v1/chat/completions"
        model = self.config.get("selected_model", {}).get("ollama", "llama3.2")
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "stream": True
        }
        return self._stream_openai_compatible(url, headers, payload, on_token)

    def _stream_openai_compatible(self, url, headers, payload, on_token):
        """Helper to stream from any OpenAI-compatible completions endpoint."""
        full_text = ""
        try:
            res = requests.post(url, headers=headers, json=payload, stream=True, timeout=20)
            if res.status_code != 200:
                try:
                    err_msg = res.json().get("error", {}).get("message", res.text[:200])
                except Exception:
                    err_msg = res.text[:200]
                err = f"[API Error {res.status_code}]: {err_msg}"
                print(f"[API] Error: {err}")
                if on_token:
                    on_token(f"*({err}. Using offline fallback...)*\n\n")
                return self._ask_demo(question, on_token)

            for line in res.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    body = line_str[6:].strip()
                    if body == "[DONE]":
                        break
                    try:
                        chunk = json.loads(body)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_text += content
                                if on_token:
                                    on_token(content)
                    except Exception:
                        pass
            return full_text
        except Exception as e:
            err = f"[API Error]: {e}"
            if on_token: on_token(err)
            return err
