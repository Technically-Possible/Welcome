<?php
// Lists the images in this folder for the Art Hall of Fame. No need to edit.
header('Content-Type: application/json');
header('Cache-Control: no-store');
$files = array();
foreach (scandir(__DIR__) as $f) {
  if (preg_match('/\.(png|jpe?g|webp|gif|avif)$/i', $f)) { $files[] = $f; }
}
echo json_encode($files);
