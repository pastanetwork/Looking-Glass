var LG_ASCII = `
              :::::::::                      :::::::::
          ::::::::::::::::::            ::::::::::::::::::
           :::::::::::::::::::        :::::::::::::::::::
           :::::::           ::     ::::::::::    :::::::
            :::::::                ::::::::      :::::::
             :::::::              :::::::       :::::::
            ::::::::             :::::::        ::::::::
          ::::::::               ::::::           ::::::::
         ::::::::               ::::::              ::::::::
      :::::::::                ::::::                :::::::::
       ::::::::                ::::::                ::::::::
         ::::::::             ::::::               ::::::::
           ::::::::          ::::::               :::::::
            ::::::::        ::::::              ::::::::
             ::::::       :::::::                ::::::
            :::::::     ::::::::    :            :::::::
           ::::::::::::::::::::      :::          :::::::
           :::::::::::::::::::        ::::::::::::::::::::
          :::::::::::::::::              :::::::::::::::::
              :::::::::                      :::::::::
`;

function printAsciiArt() {
    console.log("%c" + LG_ASCII, "color: #ffd700");
    console.log(
        "%cPastanetwork Looking Glass%c\n" +
        "Outil de diagnostic réseau open-source — https://github.com/pastanetwork/Looking-Glass",
        "color: #ffd700; font-weight: 700; font-size: 14px",
        "color: #8a8a8a; font-size: 12px"
    );
}

window.addEventListener("load", function () {
    printAsciiArt();
});
