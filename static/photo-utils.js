/* ============================================================
   photo-utils.js — comprime fotos no navegador antes de enviar
   (evita ultrapassar o limite de tamanho e deixa tudo mais rápido)
   ============================================================ */

/**
 * Redimensiona e comprime um arquivo de imagem (ou uma data URI já existente)
 * usando um <canvas>, devolvendo um novo File em JPEG.
 * maxDim = maior dimensão permitida (largura ou altura), em pixels.
 * qualidade = 0 a 1 (qualidade JPEG).
 */
function comprimirImagem(entrada, maxDim = 1600, qualidade = 0.82) {
  return new Promise((resolve, reject) => {
    const img = new Image();

    img.onload = () => {
      let { width, height } = img;

      if (width > maxDim || height > maxDim) {
        if (width > height) {
          height = Math.round(height * (maxDim / width));
          width = maxDim;
        } else {
          width = Math.round(width * (maxDim / height));
          height = maxDim;
        }
      }

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      canvas.getContext('2d').drawImage(img, 0, 0, width, height);

      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error('Falha ao comprimir imagem'));
          return;
        }
        const nomeBase = (entrada.name || 'foto').replace(/\.[^.]+$/, '');
        resolve(new File([blob], `${nomeBase}.jpg`, { type: 'image/jpeg' }));
      }, 'image/jpeg', qualidade);
    };

    img.onerror = () => reject(new Error('Não foi possível ler a imagem'));

    if (typeof entrada === 'string') {
      // já é uma data URI (foto existente)
      img.src = entrada;
    } else {
      // é um File vindo de um <input type="file">
      const reader = new FileReader();
      reader.onload = (e) => { img.src = e.target.result; };
      reader.onerror = () => reject(new Error('Não foi possível ler o arquivo'));
      reader.readAsDataURL(entrada);
    }
  });
}

/** Converte uma data URI em um File comprimido (usado pra "reduzir" fotos antigas grandes). */
async function comprimirDataUri(dataUri, maxDim = 1600, qualidade = 0.82) {
  const file = await comprimirImagem(dataUri, maxDim, qualidade);
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
}
