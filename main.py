import time
import gen_post_page
import instagram
import facebook
import argparse


def main(dry_run=False):
    # 1. Generate the Instagram post content (caption) and image URL
    post, image_url = gen_post_page.main()
    
    print("\nGenerated Post Content:")
    print(post)
    print("\nGenerated Image URL:")
    print(image_url)

    if dry_run:
        print("\n[DRY RUN] Skipping actual posting to Instagram and Facebook.")
        return

    # 2. Post to Instagram
    instagram.post_to_instagram(image_url, post)
    
    # 3. Wait 5 seconds before posting to Facebook
    time.sleep(5)
    
    # 4. Post to Facebook
    facebook.post_to_facebook(post, image_url)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the social media posting workflow.")
    parser.add_argument("--dry-run", action="store_true", help="Run the workflow without posting to IG and FB")
    args = parser.parse_args()

    main(dry_run=args.dry_run)