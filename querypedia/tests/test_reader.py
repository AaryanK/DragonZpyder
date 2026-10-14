"""Run with: python -m unittest discover -s tests -v (from querypedia)."""
import unittest
from fastapi import HTTPException

from main import clean_html, excerpts, local_wiki_link, normalized_title, safe_url


class QuerypediaTests(unittest.TestCase):
    def test_existing_wikipedia_paths(self):
        self.assertEqual(local_wiki_link("Alan Turing"), "/wiki/Alan_Turing")
        self.assertEqual(safe_url("./Alan_Turing"), "/wiki/Alan_Turing")
        self.assertEqual(safe_url("https://en.wikipedia.org/wiki/Nepal#History"),
                         "/wiki/Nepal#History")
        self.assertEqual(safe_url("#History"), "#History")

    def test_normalization_and_invalid_titles(self):
        self.assertEqual(normalized_title("Quantum_mechanics"), "Quantum mechanics")
        with self.assertRaises(HTTPException):
            normalized_title("<script>")
        with self.assertRaises(HTTPException):
            normalized_title("")

    def test_unsafe_html_and_images_are_removed(self):
        html, chunks = clean_html(
            '<html><body><script>alert(1)</script><style>p{display:none}</style>'
            '<h2 id="Life">Life</h2><p>A useful, fairly long paragraph on the history of an article.</p>'
            '<a href="./Ada_Lovelace">Ada</a>'
            '<img src="https://evil.example/track.png"></body></html>')
        self.assertNotIn("<script", html)
        self.assertNotIn("alert(1)", html)
        self.assertNotIn("evil.example", html)
        self.assertIn('href="/wiki/Ada_Lovelace"', html)
        self.assertEqual(chunks[0]["heading"], "Life")

    def test_relevant_excerpts(self):
        chunks = [
            {"heading":"Overview","text":"The topic is a general introduction.","anchor":""},
            {"heading":"History","text":"Researcher studied neutrino oscillations.","anchor":"History"},
            {"heading":"Architecture","text":"Computer architectures are different.","anchor":"Architecture"},
        ]
        self.assertIn("neutrino oscillations", excerpts(chunks, "What about neutrino oscillations?"))


if __name__ == "__main__":
    unittest.main()
