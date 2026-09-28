ART HALL OF FAME - how to add art
==================================

Drop an image into this folder, named like this:

    Message about the image- Artist name- social link.png

The page splits the name at each "- " (a dash followed by a space), so
the message can be as long as you like. Filenames can't contain "/" or
":", so write the social link one of these two ways:

1. platform@handle  (easiest)
     Chilling in my chair- AH- instagram@ahdraws.png
     Beach day- Sam- x@samdraws.jpg
   Supported: instagram, x (or twitter), bsky, furaffinity (or fa),
   deviantart (or da), kofi, tumblr, artstation, youtube, twitch,
   tiktok, threads, patreon, vgen, toyhouse, carrd

2. a web address with "!" wherever there'd be a "/"
     Warp core PJs- Rin- rin-art.com!gallery.png
     -> links to https://rin-art.com/gallery

Images show in filename order. To choose the order, start the message
with a number, e.g. "01 First commission- ...".

HOW THE PAGE FINDS THE IMAGES
The page tries these in order, so at least one needs to work on your host:
  1. list.php (this folder) - works on any host with PHP.
  2. The server's folder listing (Apache/nginx "autoindex").
  3. list.txt - if neither works, put one filename per line in a file
     called list.txt in this folder.
