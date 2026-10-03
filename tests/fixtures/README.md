# Test fixtures

| File | Origin |
|---|---|
| `PriceFull7290876100000-003-202410070010.gz` | Real chain file from Sefi Erlich's [israeli-supermarket-scarpers](https://github.com/OpenIsraeliSupermarkets/israeli-supermarket-scarpers) test suite. **Changed:** cut to its first 40 KB, so it is a truncated gzip on purpose (tests recovery). |
| `PriceFull7290172900007-083-202409270311.xml` | Real chain file (`<OrderXml>/<Line>` layout) from Sefi Erlich's [israeli-supermarket-parsers](https://github.com/OpenIsraeliSupermarkets/israeli-supermarket-parsers). **Changed:** trimmed to the first 30 items. |
| `PromoFull7290172900007-350-202410030634.xml` | Same repository, unchanged (an empty promo file). |
| `Stores7290027600007-…xml`, `Stores7290058140886-…xml`, `PromoFull7290058140886-…xml` | Written for this project to reproduce published layouts (SAP upper-case export, UTF-16 nested sub-chains, Windows-1255 promotions). Store and promo values are illustrative. |

Files from Sefi Erlich's repositories are used for non-commercial testing under their license, with attribution.
