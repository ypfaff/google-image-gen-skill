#!/usr/bin/env python3
"""Google Gemini Image Generator.

Generate images from text prompts or edit existing images using Google's Gemini API.
Supports reference images and style templates for consistency.

This script is part of the google-image-gen Claude Code skill.

Setup:
    1. Get API key from https://aistudio.google.com/apikey
    2. Create .env file in skill directory with: GOOGLE_AI_API_KEY=your_key_here
    3. Run: uv sync (or pip install google-genai python-dotenv pillow)

Usage:
    # Generate from prompt
    uv run python main.py output.png "A minimal 3D cube on solid black background"

    # Use a style template (reads prompt from .md file)
    uv run python main.py output.png "A gear icon" --style styles/blue_glass_3d.md

    # Generate multiple variations with style
    uv run python main.py output.png "cube" "sphere" "pyramid" --style styles/blue_glass_3d.md

    # Edit existing image
    uv run python main.py output.png "Change the background to blue" --edit input.png

    # Use reference images for style consistency
    uv run python main.py output.png "Same style but with a sphere" --ref style.png

    # Specify aspect ratio
    uv run python main.py output.png "Prompt" --aspect 16:9

Aspect ratios: 1:1, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9
"""
import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image


def load_style_template(style_path: Path) -> str:
    """Load a prompt template from a markdown style file.

    Looks for a code block after '## Prompt Template' or '### Template'.
    The template should contain {subject} as a placeholder.

    Args:
        style_path: Path to the .md style file.

    Returns:
        The prompt template string with {subject} placeholder.

    Raises:
        FileNotFoundError: If style file doesn't exist.
        ValueError: If no prompt template found in file.
    """
    if not style_path.exists():
        raise FileNotFoundError(f"Style file not found: {style_path}")

    content = style_path.read_text()

    # Look for code block after "Prompt Template" or "Template" header
    pattern = (
        r'(?:##?\s*(?:Prompt\s*)?Template)[^\n]*\n+(?:.*?\n)*?```[^\n]*\n(.*?)```'
    )
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

    if match:
        template = match.group(1).strip()
        # Normalize the placeholder
        template = re.sub(
            r'\[YOUR SUBJECT[^\]]*\]|\[SUBJECT\]|\{subject\}',
            '{subject}',
            template,
            flags=re.IGNORECASE
        )
        return template

    raise ValueError(
        f"No prompt template found in {style_path}. "
        "Add a '## Prompt Template' section with a code block."
    )


def apply_style_template(template: str, subject: str) -> str:
    """Apply a subject to a style template.

    Args:
        template: The prompt template with {subject} placeholder.
        subject: The subject to insert.

    Returns:
        The complete prompt.
    """
    if '{subject}' in template:
        return template.format(subject=subject)
    # If no placeholder, prepend the subject
    return f"{subject}. {template}"


def edit_image(
    input_path: Path,
    prompt: str,
    output_path: Path,
    reference_images: Optional[list[Path]] = None,
) -> bool:
    """Edit an existing image based on a text prompt.

    Args:
        input_path: Path to the image to edit.
        prompt: Text description of the edit to make.
        output_path: Where to save the edited image.
        reference_images: Optional list of additional reference images.

    Returns:
        True if image was saved successfully, False otherwise.
    """
    client = genai.Client(
        api_key=os.environ.get("GOOGLE_AI_API_KEY"),
    )

    contents: list = [prompt]
    main_image = Image.open(input_path)
    contents.append(main_image)

    if reference_images:
        for ref_path in reference_images[:13]:  # 13 refs + 1 main = 14 max
            if ref_path.exists():
                contents.append(Image.open(ref_path))
            else:
                print(f"Warning: Reference image not found: {ref_path}")

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    if (response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts):
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                with open(output_path, "wb") as f:
                    f.write(part.inline_data.data)
                print(f"Edited image saved to: {output_path}")
                return True
            if hasattr(part, "text") and part.text:
                print(part.text)

    return False


def generate_image(
    prompt: str,
    output_path: Path,
    reference_images: Optional[list[Path]] = None,
    aspect_ratio: str = "16:9",
) -> bool:
    """Generate a new image from a text prompt.

    Args:
        prompt: Text description of the image to generate.
        output_path: Where to save the generated image.
        reference_images: Optional list of reference images.
        aspect_ratio: Aspect ratio for the image.

    Returns:
        True if image was saved successfully, False otherwise.
    """
    client = genai.Client(
        api_key=os.environ.get("GOOGLE_AI_API_KEY"),
    )

    if reference_images:
        contents: list = [prompt]
        for ref_path in reference_images[:14]:
            if ref_path.exists():
                contents.append(Image.open(ref_path))
            else:
                print(f"Warning: Reference image not found: {ref_path}")

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        if (response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts):
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    with open(output_path, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"Image saved to: {output_path}")
                    return True
                if hasattr(part, "text") and part.text:
                    print(part.text)
    else:
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ]

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size="1K",
            ),
        )

        for chunk in client.models.generate_content_stream(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=config,
        ):
            if (chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None):
                continue

            part = chunk.candidates[0].content.parts[0]
            if part.inline_data and part.inline_data.data:
                with open(output_path, "wb") as f:
                    f.write(part.inline_data.data)
                print(f"Image saved to: {output_path}")
                return True
            if hasattr(part, "text") and part.text:
                print(part.text)

    return False


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Generate images using Google Gemini API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py output.png "A minimal geometric cube"
  python main.py output.png "gear icon" --style styles/blue_glass_3d.md
  python main.py output.png "cube" "sphere" --style styles/blue_glass_3d.md
  python main.py output.png "Make it green" --edit input.png
  python main.py output.png "Similar style" --ref style.png
        """,
    )
    parser.add_argument(
        "output",
        help="Output path for the image",
    )
    parser.add_argument(
        "prompts",
        nargs="+",
        help="One or more subjects/prompts",
    )
    parser.add_argument(
        "--style", "-s",
        help="Path to style template .md file",
    )
    parser.add_argument(
        "--edit", "-e",
        help="Path to input image to edit",
    )
    parser.add_argument(
        "--ref", "-r",
        action="append",
        dest="references",
        help="Reference image (can be used multiple times, up to 14)",
    )
    parser.add_argument(
        "--aspect", "-a",
        default="16:9",
        choices=["1:1", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
        help="Aspect ratio (default: 16:9)",
    )
    args = parser.parse_args()

    # Load .env from script directory first, then current directory
    script_dir = Path(__file__).parent
    env_path = script_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    load_dotenv()  # Also try current directory

    if not os.environ.get("GOOGLE_AI_API_KEY"):
        print("Error: GOOGLE_AI_API_KEY not found in environment")
        print("Create a .env file with: GOOGLE_AI_API_KEY=your_key_here")
        print("Get your API key from: https://aistudio.google.com/apikey")
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load style template if provided
    style_template = None
    if args.style:
        style_path = Path(args.style)
        # If relative path, check relative to script directory first
        if not style_path.is_absolute() and not style_path.exists():
            script_relative = script_dir / style_path
            if script_relative.exists():
                style_path = script_relative

        try:
            style_template = load_style_template(style_path)
            print(f"Loaded style template from: {style_path}")
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
            return 1

    # Process prompts
    prompts = args.prompts
    if style_template:
        prompts = [apply_style_template(style_template, p) for p in prompts]

    ref_images = [Path(r) for r in args.references] if args.references else None

    if args.edit:
        input_path = Path(args.edit)
        if not input_path.exists():
            print(f"Error: Input image not found: {input_path}")
            return 1
        edit_image(input_path, prompts[0], output_path, reference_images=ref_images)
    elif len(prompts) == 1:
        generate_image(
            prompts[0],
            output_path,
            reference_images=ref_images,
            aspect_ratio=args.aspect,
        )
    else:
        stem = output_path.stem
        suffix = output_path.suffix
        parent = output_path.parent

        for i, prompt in enumerate(prompts, 1):
            numbered_path = parent / f"{stem}_{i}{suffix}"
            print(f"\nGenerating image {i}/{len(prompts)}...")
            generate_image(
                prompt,
                numbered_path,
                reference_images=ref_images,
                aspect_ratio=args.aspect,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())