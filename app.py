import streamlit as st
from groq import Groq
import tweepy
import os

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hashtag Roaster",
    page_icon="🔥",
    layout="centered",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0d0d0d; color: #f0f0f0; }
    h1 { color: #ff4e4e; font-size: 2.5rem; }
    .verdict { font-size: 1.8rem; font-weight: bold; padding: 1rem;
               border-radius: 8px; text-align: center; margin: 1rem 0; }
    .bullish  { background: #1a3a1a; color: #4cff72; border: 1px solid #4cff72; }
    .bearish  { background: #3a1a1a; color: #ff4e4e; border: 1px solid #ff4e4e; }
    .neutral  { background: #2a2a1a; color: #ffd700; border: 1px solid #ffd700; }
    .tweet-box { background: #1a1a1a; border-left: 3px solid #555;
                 padding: 0.5rem 1rem; margin: 0.3rem 0;
                 border-radius: 4px; font-size: 0.85rem; }
    .score { font-size: 0.9rem; color: #888; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔥 Hashtag Roaster")
st.write("Drop any hashtag and I'll tell you if Twitter is bullish, pissed, or just meh about it.")

# ── Input ─────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    hashtag = st.text_input("Hashtag (no #)", placeholder="Bitcoin", label_visibility="collapsed")
with col2:
    go = st.button("🔥 Roast it", use_container_width=True)

tweet_count = st.slider("How many tweets to analyze?", 10, 100, 30, step=10)

# ── Core logic ────────────────────────────────────────────────────────────────
def get_api_clients():
    """Pull keys from Streamlit secrets or environment variables."""
    bearer = st.secrets.get("TWITTER_BEARER") or os.getenv("TWITTER_BEARER")
    groq_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

    if not bearer:
        raise ValueError("Missing TWITTER_BEARER — add it to Streamlit secrets.")
    if not groq_key:
        raise ValueError("Missing GROQ_API_KEY — add it to Streamlit secrets.")

    twitter = tweepy.Client(bearer_token=bearer, wait_on_rate_limit=True)
    groq = Groq(api_key=groq_key)
    return twitter, groq


def fetch_tweets(twitter_client, hashtag: str, count: int) -> list[str]:
    """Fetch recent tweets for a hashtag. Returns list of text strings."""
    count = max(10, min(count, 100))  # clamp between API limits
    response = twitter_client.search_recent_tweets(
        query=f"#{hashtag} -is:retweet lang:en",
        max_results=count,
        tweet_fields=["text"],
    )
    if not response.data:
        return []
    return [tweet.text for tweet in response.data]


def analyze_sentiment(groq_client, hashtag: str, tweets: list[str]) -> dict:
    """Send tweets to Groq/Llama and get a structured sentiment result."""
    joined = " | ".join(tweets[:50])  # cap at 50 to stay within token limits

    prompt = f"""You are a blunt, no-BS sentiment analyst.
Analyze the sentiment of these tweets about #{hashtag}.

Respond in this EXACT format (nothing else):
VERDICT: <bullish|bearish|neutral>
SCORE: <number from -100 to 100>
REASON: <one punchy sentence, max 20 words>

Tweets:
{joined}"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()

    # Parse structured response
    result = {"verdict": "neutral", "score": 0, "reason": "Could not parse response."}
    for line in raw.splitlines():
        if line.startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip().lower()
            if verdict in ("bullish", "bearish", "neutral"):
                result["verdict"] = verdict
        elif line.startswith("SCORE:"):
            try:
                result["score"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()

    return result


# ── Run analysis ───────────────────────────────────────────────────────────────
if go:
    if not hashtag.strip():
        st.error("Enter a hashtag first.")
    else:
        hashtag = hashtag.strip().lstrip("#")

        with st.spinner(f"Scanning Twitter for #{hashtag}..."):
            try:
                twitter, groq_client = get_api_clients()
                tweets = fetch_tweets(twitter, hashtag, tweet_count)

                if not tweets:
                    st.warning(f"No recent tweets found for #{hashtag}. Try a different tag.")
                else:
                    result = analyze_sentiment(groq_client, hashtag, tweets)

                    verdict = result["verdict"]
                    score = result["score"]
                    reason = result["reason"]

                    # Verdict labels
                    labels = {
                        "bullish": "📈 BULLISH AS FUCK",
                        "bearish": "📉 PEOPLE ARE PISSED",
                        "neutral": "😐 MEH, NOBODY CARES",
                    }

                    st.markdown(
                        f'<div class="verdict {verdict}">{labels[verdict]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="score">Sentiment score: {score}/100 — {reason}</div>', unsafe_allow_html=True)

                    # Show sample tweets
                    st.markdown("---")
                    st.markdown(f"**Sample tweets analyzed ({len(tweets)} total):**")
                    for t in tweets[:8]:
                        st.markdown(f'<div class="tweet-box">{t}</div>', unsafe_allow_html=True)

            except ValueError as e:
                st.error(str(e))
            except tweepy.TooManyRequests:
                st.error("Twitter rate limit hit. Wait a few minutes and try again.")
            except tweepy.Unauthorized:
                st.error("Twitter API key is invalid or expired. Check your TWITTER_BEARER secret.")
            except Exception as e:
                st.error(f"Something broke: {str(e)}")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div style="text-align:center; color:#555; font-size:0.8rem;">Built with Tweepy + Groq/Llama + Streamlit</div>', unsafe_allow_html=True)
