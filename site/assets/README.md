# Site assets

Provenance and licence for every image shipped with the website. Anything added
here needs the same, so that the repository can always answer "where did that
come from and may we use it?".

Note that the repository's own CC BY 4.0 licence does **not** apply to the files
in this directory. They are third-party works included under their own terms,
recorded below. Do not add anything here whose licence you cannot state.

## masthead-baltic-bloom.jpg

The banner behind the site title.

|   |   |
|---|---|
| **Subject** | Cyanobacteria bloom in the Baltic Sea, south of Gotland |
| **Instrument** | Landsat 8, Operational Land Imager (OLI) |
| **Acquired** | 15 August 2020 |
| **Source page** | <https://science.nasa.gov/earth/earth-observatory/beguiling-bloom-in-the-baltic-sea-147135> |
| **Original file** | `baltic_oli_2020228_lrg.jpg`, 8723 × 5815 px |
| **This file** | wide crop of the upper band, resized to 2000 × 667, JPEG quality 72 |

**Credit line:** NASA Earth Observatory image by Joshua Stevens, using Landsat
data from the U.S. Geological Survey.

### Licence

Public domain. The underlying Landsat data is produced by the U.S. Geological
Survey and the image was produced by NASA Earth Observatory; works created by the
U.S. federal government are not subject to copyright in the United States. NASA
[asks that NASA be acknowledged as the source](https://www.nasa.gov/nasa-brand-center/images-and-media/),
which the footer of the site does.

The exceptions in NASA's media guidelines do not apply here: the image carries no
NASA insignia or logotype, contains no identifiable people, and the source page
indicates no third-party copyright.

It is a picture of marine microbes taken from orbit, which is as close to
on-topic as a banner for this catalogue can get.

### Reproducing the crop

```sh
curl -O https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/147000/147135/baltic_oli_2020228_lrg.jpg

python3 - <<'PY'
from PIL import Image
im = Image.open("baltic_oli_2020228_lrg.jpg")
W, H = im.size
crop_w = int(W * 0.82)
crop_h = crop_w // 3
banner = im.crop((0, int(H * 0.06), crop_w, int(H * 0.06) + crop_h))
banner.resize((2000, 667), Image.LANCZOS).save(
    "masthead-baltic-bloom.jpg", "JPEG", quality=72, optimize=True, progressive=True)
PY
```

The image sits behind a dark gradient scrim in `site/style.css`, so it is
compressed fairly hard on purpose: JPEG artefacts are not visible through the
overlay, and the banner is on every page load.
